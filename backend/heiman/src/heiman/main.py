import logging
import asyncio
import time
from uuid import uuid4
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pathlib import Path

from heiman.config import get_settings, init_logging
from heiman.database import init_database
from heiman.data.initial_data import initialize_data
from heiman.manager import get_manager
from heiman.middleware.exception_handler import handle_exception
from heiman.node_monitor import get_monitor, ResourceMonitor, WatchdogTask
from heiman.router.auth_router import router as auth_router
from heiman.router.device_router import router as device_router
from heiman.router.event_router import router as event_router
from heiman.router.home_router import router as home_router
from heiman.router.log_router import router as log_router
from heiman.router.model_router import router as model_router
from heiman.router.monitor_router import router as monitor_router, set_resource_monitor
from heiman.router.observability_router import router as observability_router
from heiman.router.person_router import router as person_router
from heiman.router.rule_router import router as rule_router
from heiman.router.room_router import router as room_router
from heiman.router.sensor_router import router as sensor_router
from heiman.router.task_router import router as task_router
from heiman.router.product_router import router as product_router
from heiman.router.ai_router import router as ai_router
from heiman.admin.router import router as admin_router
from heiman.home_profile.router import router as home_profile_router

logger = logging.getLogger(__name__)

_BG_TASKS: set[asyncio.Task[object]] = set()


async def _periodic_refresh(interval: int):
    logger.info("Starting periodic refresh task with interval %d seconds", interval)

    while True:
        try:
            mgr = get_manager()
            if not getattr(mgr, '_offline_mode', False):
                cycle_start = time.time()
                sensor_data_list = await mgr.api_client.get_sensor_data()

                for sensor_data in sensor_data_list:
                    mgr.sensor_log_repo.insert(sensor_data)
                    await mgr.rule_engine.run_rules(sensor_data)

                cycle_ms = (time.time() - cycle_start) * 1000
                logger.debug("Processed %d sensor data points in %.1fms", len(sensor_data_list), cycle_ms)

                try:
                    from heiman.observability.recorder import get_recorder
                    recorder = get_recorder()
                    if recorder:
                        recorder.record_cycle(
                            trace_id=str(uuid4()),
                            timestamp=int(time.time() * 1000),
                            device_count=len(sensor_data_list),
                            cycle_total_ms=cycle_ms,
                            pipeline_total_ms=cycle_ms,
                        )
                except Exception:
                    pass
            else:
                logger.debug("Skipping periodic refresh (offline mode)")

            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("Periodic refresh task cancelled")
            raise
        except Exception as e:
            logger.error("Periodic refresh failed: %s", e)
            await asyncio.sleep(interval)


async def _cleanup_loop() -> None:
    logger.info("Starting cleanup task")

    await asyncio.sleep(3600)

    while True:
        try:
            from heiman.database.connector import get_db_connector

            connector = get_db_connector()
            settings = get_settings()
            max_days = getattr(settings.logging, 'log_ttl_days', 30)

            deleted = connector.cleanup_old_logs(max_days)
            logger.info("Cleanup: deleted %d old records", deleted)

            connector.incremental_vacuum()
            logger.info("Cleanup: incremental vacuum completed")

        except Exception as e:
            logger.error("Cleanup loop error: %s", e)

        await asyncio.sleep(86400)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_logging()
    init_database()
    initialize_data()

    settings = get_settings()

    obs_db_path = str(settings.logging.log_dir.parent / "observability.db")
    app.state.obs_db_path = obs_db_path

    try:
        from heiman.observability.metrics_db import connect, init_schema
        from heiman.observability.recorder import init_recorder
        obs_conn = connect(obs_db_path)
        init_schema(obs_conn)
        obs_conn.close()
        init_recorder(obs_db_path)
        logger.info("Observability database initialized at %s", obs_db_path)
    except Exception as e:
        logger.error("Failed to initialize observability database: %s", e)

    mon = get_monitor()
    mon.register("sensor", "SOURCE", watchdog_s=60)
    mon.register("collector", "WINDOW", watchdog_s=60)
    mon.register("classifier", "WINDOW", watchdog_s=60)
    mon.register("rule_engine", "EVENT", watchdog_s=60)
    mon.register("api_client", "SERVICE")

    try:
        await get_manager().initialize()
        logger.info("Manager initialization completed")
    except Exception as e:
        logger.error("Manager initialization failed: %s", e)
        raise

    watchdog = WatchdogTask(mon)
    watchdog.start()

    resource_mon = ResourceMonitor(
        db_path=str(settings.logging.log_dir.parent / "heiman.db"),
        log_dir=str(settings.logging.log_dir),
    )
    resource_mon.start()
    set_resource_monitor(resource_mon, start_time=time.monotonic())

    _refresh_task = asyncio.create_task(_periodic_refresh(settings.sensor.sync_interval_seconds))
    _BG_TASKS.add(_refresh_task)
    _refresh_task.add_done_callback(_BG_TASKS.discard)

    _cleanup_task = asyncio.create_task(_cleanup_loop())
    _BG_TASKS.add(_cleanup_task)
    _cleanup_task.add_done_callback(_BG_TASKS.discard)

    logger.info("Heiman Agent started successfully")

    yield

    watchdog.enter_shutdown()

    _refresh_task.cancel()
    _cleanup_task.cancel()
    try:
        await _refresh_task
    except asyncio.CancelledError:
        pass
    try:
        await _cleanup_task
    except asyncio.CancelledError:
        pass

    watchdog.stop()
    resource_mon.stop()

    logger.info("Heiman Agent shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Heiman Agent API",
        version="1.0.0",
        description="海曼传感器智能Agent API",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def catch_all_exceptions_middleware(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            return handle_exception(request, exc)

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        """请求日志中间件，记录每个 API 请求的详细信息"""
        start_time = time.time()
        path = request.url.path
        method = request.method

        # 记录请求开始
        if path.startswith("/") and not path.startswith("/docs") and not path.startswith("/redoc") and not path.startswith("/openapi"):
            logger.info(">>> %s %s | client=%s", method, path, request.client.host if request.client else "unknown")

        response = await call_next(request)

        # 记录请求完成
        duration_ms = (time.time() - start_time) * 1000
        if path.startswith("/") and not path.startswith("/docs") and not path.startswith("/redoc") and not path.startswith("/openapi"):
            logger.info(
                "<<< %s %s | status=%d | duration=%.1fms",
                method, path, response.status_code, duration_ms
            )
            try:
                from heiman.service.observability_service import ObservabilityService
                obs = ObservabilityService.get_instance()
                error = response.status_code >= 400
                obs.record_request(path, duration_ms, error=error)
            except Exception:
                pass

        return response

    app.include_router(auth_router, prefix="/api")
    app.include_router(sensor_router, prefix="/api")
    app.include_router(event_router, prefix="/api")
    app.include_router(rule_router, prefix="/api")
    app.include_router(monitor_router, prefix="/api")
    app.include_router(home_router, prefix="/api")
    app.include_router(log_router, prefix="/api")
    app.include_router(model_router, prefix="/api")
    app.include_router(device_router, prefix="/api")
    app.include_router(person_router, prefix="/api")
    app.include_router(room_router, prefix="/api")
    app.include_router(task_router, prefix="/api")
    app.include_router(observability_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")
    app.include_router(home_profile_router, prefix="/api")
    app.include_router(product_router, prefix="/api")
    app.include_router(ai_router, prefix="/api")

    @app.get("/health")
    async def health_check():
        try:
            mon = get_monitor()
            for state in mon.iter_states():
                if state.lifecycle in ("FAILED", "STALLED"):
                    return JSONResponse(status_code=503, content={"status": "unhealthy"})
            return {"status": "healthy", "service": "heiman-agent"}
        except Exception:
            logger.exception("health monitor check failed")
            return JSONResponse(status_code=503, content={"status": "unknown"})

    @app.get("/{full_path:path}")
    async def spa_handler(full_path: str, request: Request):
        norm = full_path.rstrip("/").lower()
        if norm == "api" or norm.startswith("api/") or norm == "health":
            return Response(status_code=404, content="404 Not Found")

        static_dir = settings.directories.static_dir
        static_root = static_dir.resolve()

        if full_path and norm != "index.html":
            try:
                real_file = (static_dir / full_path).resolve()
                real_file.relative_to(static_root)
            except (ValueError, OSError):
                logger.warning("spa_handler path-traversal blocked: %r", full_path[:200])
                return Response(status_code=404, content="404 Not Found")
            if real_file.is_file():
                headers: dict[str, str] = {}
                if full_path.startswith("assets/"):
                    headers["Cache-Control"] = "public, max-age=31536000, immutable"
                elif full_path.startswith("vendor/") or full_path.startswith("fonts/"):
                    headers["Cache-Control"] = "public, max-age=86400"
                elif full_path.startswith("locales/"):
                    headers["Cache-Control"] = "public, max-age=3600"
                return FileResponse(str(real_file), headers=headers or None)

        index_file = static_dir / "index.html"
        if not index_file.exists():
            return Response(status_code=404, content="404 Not Found")

        token = settings.server.token
        if not token:
            return HTMLResponse(
                content="<h1>503: server.token 未配置,无法启动 web 页</h1>",
                status_code=503,
            )

        template = index_file.read_text(encoding="utf-8")
        template = template.replace(
            "__HEIMAN_INJECT_TOKEN_HERE__", token
        )
        return HTMLResponse(template, headers={"Cache-Control": "no-store"})

    return app


app = create_app()


def start_server():
    import uvicorn
    settings = get_settings()

    logger.info("Starting Heiman Agent server on %s:%d", settings.server.host, settings.server.port)

    uvicorn.run(
        "heiman.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=True,
        log_level=settings.logging.level.lower(),
    )


if __name__ == "__main__":
    start_server()