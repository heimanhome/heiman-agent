import os
import time
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from heiman.middleware.auth_middleware import verify_token
from heiman.node_monitor import get_monitor, ResourceMonitor

router = APIRouter(prefix="/monitor", tags=["Monitor"])

_resource_monitor: ResourceMonitor | None = None
_start_time: float | None = None


def set_resource_monitor(monitor: ResourceMonitor, start_time: float | None = None) -> None:
    global _resource_monitor, _start_time
    _resource_monitor = monitor
    if start_time is not None:
        _start_time = start_time


def _get_uname() -> str | None:
    try:
        u = os.uname()
    except (AttributeError, OSError):
        return None
    return f"{u.sysname} {u.nodename} {u.release} {u.version} {u.machine}"


@router.get("/status", dependencies=[Depends(verify_token)])
async def get_monitor_meta():
    """Process-level meta: node_count / uptime_s / uname / resources."""
    mon = get_monitor()
    data: dict = {
        "node_count": len(mon.iter_states()),
    }
    if _start_time is not None:
        data["uptime_s"] = round(time.monotonic() - _start_time, 1)
    uname = _get_uname()
    if uname is not None:
        data["uname"] = uname
    if _resource_monitor is not None:
        data["resources"] = _resource_monitor.get_data()
    return {"success": True, "data": data}


@router.get("/nodes", dependencies=[Depends(verify_token)])
async def get_nodes():
    mon = get_monitor()
    return {"success": True, "data": {"ts": time.time(), "nodes": mon.snapshot()}}


@router.get("/nodes/{name}", dependencies=[Depends(verify_token)])
async def get_node(name: str):
    mon = get_monitor()
    result = mon.snapshot_one(name)
    if result is None:
        return JSONResponse(
            status_code=404, content={"success": False, "message": f"node '{name}' not found"}
        )
    return {"success": True, "data": result}


@router.get("/resources", dependencies=[Depends(verify_token)])
async def get_resources():
    if _resource_monitor is None:
        return {"success": True, "data": {}}
    return {"success": True, "data": _resource_monitor.get_data()}


WindowKey = Literal["1h", "6h", "24h", "3d"]
BucketKey = Literal["1m", "5m", "1h"]
_WINDOW_SECONDS: dict[str, int] = {
    "1h": 3600,
    "6h": 21600,
    "24h": 86400,
    "3d": 259200,
}
_BUCKET_SECONDS: dict[str, int] = {"1m": 60, "5m": 300, "1h": 3600}


@router.get("/memory", dependencies=[Depends(verify_token)])
async def get_memory_snapshot():
    if _resource_monitor is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "resource monitor not initialized"},
        )
    snap = _resource_monitor.get_memory_latest()
    if snap is None:
        return {"success": True, "data": None}
    return {"success": True, "data": snap}


@router.get("/memory/series", dependencies=[Depends(verify_token)])
async def get_memory_series(
    window: WindowKey = Query("1h"),
    bucket: BucketKey = Query("1m"),
):
    if _resource_monitor is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "message": "resource monitor not initialized"},
        )
    data = _resource_monitor.get_memory_series(
        window_seconds=_WINDOW_SECONDS[window],
        bucket_seconds=_BUCKET_SECONDS[bucket],
    )
    return {"success": True, "data": data}