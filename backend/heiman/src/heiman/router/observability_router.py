from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
import logging

from heiman.middleware import verify_token
from heiman.observability.metrics_db import connect
from heiman.observability.stats import VIEWS as STATS_VIEWS

router = APIRouter(prefix="/observability", tags=["observability"])
logger = logging.getLogger(__name__)


def get_observability_service():
    from heiman.service.observability_service import ObservabilityService
    return ObservabilityService.get_instance()


@router.get("/overview", response_model=dict)
async def get_overview(
    current_user: str = Depends(verify_token),
    service=Depends(get_observability_service),
):
    """获取系统可观测性概览"""
    try:
        overview = service.get_overview()
        logger.info("Observability overview: system.cpu=%.1f%%, sensors=%d, rules=%d",
                    overview.system.cpu_percent, overview.sensor.total_sensors, overview.rule.total_rules)
        return {"success": True, "data": overview.model_dump()}
    except Exception as e:
        logger.error("Failed to get observability overview: %s", e, exc_info=True)
        return {"success": False, "message": str(e)}


@router.get("/system", response_model=dict)
async def get_system_metrics(
    current_user: str = Depends(verify_token),
    service=Depends(get_observability_service),
):
    """获取系统指标"""
    try:
        metrics = service.get_system_metrics()
        logger.debug("System metrics: cpu=%.1f%%, memory=%.1f%%, disk=%.1f%%",
                     metrics.cpu_percent, metrics.memory_percent, metrics.disk_percent)
        return {"success": True, "data": metrics.model_dump()}
    except Exception as e:
        logger.error("Failed to get system metrics: %s", e)
        return {"success": False, "message": str(e)}


@router.get("/sensor", response_model=dict)
async def get_sensor_stats(
    current_user: str = Depends(verify_token),
    service=Depends(get_observability_service),
):
    """获取传感器统计"""
    try:
        stats = service.get_sensor_stats()
        logger.debug("Sensor stats: total=%d, online=%d, data_points_today=%d",
                     stats.total_sensors, stats.online_sensors, stats.data_points_today)
        return {"success": True, "data": stats.model_dump()}
    except Exception as e:
        logger.error("Failed to get sensor stats: %s", e)
        return {"success": False, "message": str(e)}


@router.get("/rule", response_model=dict)
async def get_rule_stats(
    current_user: str = Depends(verify_token),
    service=Depends(get_observability_service),
):
    """获取规则统计"""
    try:
        stats = service.get_rule_stats()
        logger.debug("Rule stats: total=%d, enabled=%d", stats.total_rules, stats.enabled_rules)
        return {"success": True, "data": stats.model_dump()}
    except Exception as e:
        logger.error("Failed to get rule stats: %s", e)
        return {"success": False, "message": str(e)}


@router.get("/event", response_model=dict)
async def get_event_stats(
    current_user: str = Depends(verify_token),
    service=Depends(get_observability_service),
):
    """获取事件统计"""
    try:
        stats = service.get_event_stats()
        logger.debug("Event stats: total=%d, unacknowledged=%d", stats.total_events, stats.unacknowledged)
        return {"success": True, "data": stats.model_dump()}
    except Exception as e:
        logger.error("Failed to get event stats: %s", e)
        return {"success": False, "message": str(e)}


@router.get("/database", response_model=dict)
async def get_database_stats(
    current_user: str = Depends(verify_token),
    service=Depends(get_observability_service),
):
    """获取数据库统计"""
    try:
        stats = service.get_database_stats()
        logger.debug("Database stats: size=%.2f MB, tables=%d", stats.db_size_mb, stats.table_count)
        return {"success": True, "data": stats.model_dump()}
    except Exception as e:
        logger.error("Failed to get database stats: %s", e)
        return {"success": False, "message": str(e)}


@router.get("/token-usage", response_model=dict)
async def get_token_usage(
    since: int | None = None,
    until: int | None = None,
    limit: int = 10000,
    current_user: str = Depends(verify_token),
):
    """获取 Token 用量原始事件"""
    try:
        from heiman.database.token_usage_repo import get_token_usage_repo
        events, truncated = get_token_usage_repo().list_events(since, until, limit)
        return {
            "success": True,
            "data": {"events": events, "total": len(events), "truncated": truncated},
        }
    except Exception as e:
        logger.error("Failed to get token usage: %s", e)
        return {"success": False, "message": str(e)}


@router.get("/token-usage/daily", response_model=dict)
async def get_token_usage_daily(
    since: str | None = None,
    until: str | None = None,
    current_user: str = Depends(verify_token),
):
    """获取 Token 用量每日聚合"""
    try:
        from heiman.database.token_usage_repo import get_token_usage_repo
        rows = get_token_usage_repo().aggregate_daily(since, until)
        return {"success": True, "data": {"rows": rows, "total": len(rows)}}
    except Exception as e:
        logger.error("Failed to get daily token usage: %s", e)
        return {"success": False, "message": str(e)}


@router.get("/token-usage/buckets", response_model=dict)
async def get_token_usage_buckets(
    since: int | None = None,
    until: int | None = None,
    bin: int = 60,
    current_user: str = Depends(verify_token),
):
    """获取 Token 用量时间桶聚合"""
    try:
        from heiman.database.token_usage_repo import get_token_usage_repo
        rows = get_token_usage_repo().aggregate_buckets(since, until, bin)
        return {"success": True, "data": {"rows": rows, "total": len(rows)}}
    except Exception as e:
        logger.error("Failed to get token usage buckets: %s", e)
        return {"success": False, "message": str(e)}


@router.post("/token-usage/clear", response_model=dict)
async def clear_token_usage(
    current_user: str = Depends(verify_token),
):
    """清空全部 Token 用量数据"""
    try:
        from heiman.database.token_usage_repo import get_token_usage_repo
        deleted = get_token_usage_repo().clear_all()
        return {"success": True, "data": {"deleted": deleted}}
    except Exception as e:
        logger.error("Failed to clear token usage: %s", e)
        return {"success": False, "message": str(e)}


@router.get("/performance", response_model=dict)
async def get_performance_metrics(
    current_user: str = Depends(verify_token),
    service=Depends(get_observability_service),
):
    """获取性能指标（API请求延迟统计）"""
    try:
        metrics = service.get_performance_metrics()
        logger.debug("Performance metrics: total_requests=%d, total_errors=%d",
                     metrics.get("total_requests", 0), metrics.get("total_errors", 0))
        return {"success": True, "data": metrics}
    except Exception as e:
        logger.error("Failed to get performance metrics: %s", e)
        return {"success": False, "message": str(e)}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str, request: Request, current_user: str = Depends(verify_token)):
    """获取单个 trace 详情"""
    db_path = request.app.state.obs_db_path
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM traces_v WHERE trace_id=?", (trace_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "trace not found")
        cols = [d[0] for d in conn.execute("SELECT * FROM traces_v LIMIT 0").description]
        cycle = dict(zip(cols, row))

        d_rows = conn.execute(
            "SELECT * FROM traces_device WHERE cycle_id=? ORDER BY timestamp", (trace_id,)
        ).fetchall()
        d_cols = [d[0] for d in conn.execute("SELECT * FROM traces_device LIMIT 0").description]
        devices = [dict(zip(d_cols, r)) for r in d_rows]
        return {"success": True, "data": {"cycle": cycle, "devices": devices}}
    finally:
        conn.close()


@router.get("/traces")
async def list_traces(
    request: Request,
    since: int | None = None,
    until: int | None = None,
    has_agent: int | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: str = Depends(verify_token),
):
    """trace 列表（分页）"""
    db_path = request.app.state.obs_db_path
    conn = connect(db_path)
    try:
        clauses: list[str] = []
        params: list[Any] = []
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            clauses.append("timestamp <= ?")
            params.append(until)
        if has_agent is not None:
            clauses.append("has_agent_turn = ?")
            params.append(has_agent)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        # 查总数
        count_sql = f"SELECT COUNT(*) FROM traces_v {where}"
        count_row = conn.execute(count_sql, params).fetchone()
        total = count_row[0] if count_row else 0

        offset = (page - 1) * page_size
        data_sql = f"SELECT * FROM traces_v {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.append(page_size)
        params.append(offset)
        rows = conn.execute(data_sql, params).fetchall()
        cols = [d[0] for d in conn.execute("SELECT * FROM traces_v LIMIT 0").description]

        total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

        return {
            "success": True,
            "data": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "items": [dict(zip(cols, r)) for r in rows],
            },
        }
    finally:
        conn.close()


@router.get("/stats")
async def get_stats(
    request: Request,
    metric: str,
    bucket: str = "1h",
    since: int | None = None,
    until: int | None = None,
    current_user: str = Depends(verify_token),
):
    """获取统计指标"""
    view_fn = STATS_VIEWS.get(metric)
    if view_fn is None:
        raise HTTPException(400, f"unknown metric: {metric}")
    db_path = request.app.state.obs_db_path
    conn = connect(db_path)
    try:
        return {"success": True, "data": view_fn(conn, bucket, since, until)}
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        conn.close()


@router.get("/agent_runs")
@router.get("/agent-runs")
async def list_agent_runs(
    request: Request,
    since: int | None = None,
    until: int | None = None,
    source: str | None = None,
    success: int | None = None,
    trace_id: str | None = None,
    limit: int = 100,
    current_user: str = Depends(verify_token),
):
    """agent runs 列表"""
    db_path = request.app.state.obs_db_path
    conn = connect(db_path)
    try:
        clauses: list[str] = []
        params: list[Any] = []
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            clauses.append("timestamp <= ?")
            params.append(until)
        if source:
            clauses.append("source = ?")
            params.append(source)
        if success is not None:
            clauses.append("success = ?")
            params.append(success)
        if trace_id:
            clauses.append("trace_id = ?")
            params.append(trace_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM agent_runs {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        cols = [d[0] for d in conn.execute("SELECT * FROM agent_runs LIMIT 0").description]
        return {"success": True, "data": [dict(zip(cols, r)) for r in rows]}
    finally:
        conn.close()



