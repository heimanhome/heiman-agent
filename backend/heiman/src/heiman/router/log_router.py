import logging
from typing import Optional
from fastapi import APIRouter, Query, Depends
from heiman.database.log_repo import SystemLogRepo, get_log_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=dict)
async def get_logs(
    level: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    user: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    log_repo: SystemLogRepo = Depends(get_log_repo),
):
    try:
        logs = log_repo.query(
            level=level,
            action=action,
            user=user,
            search=search,
            limit=100,
        )
        logger.info("[LOG API] Query logs - level=%s, action=%s, user=%s, count=%d", level, action, user, len(logs))
        return {"success": True, "data": logs}
    except Exception as e:
        logger.error("[LOG API] Failed to get logs: %s", e)
        return {"success": False, "data": [], "message": str(e)}


@router.get("/operation", response_model=dict)
async def get_operation_logs(
    search: Optional[str] = Query(None),
    log_repo: SystemLogRepo = Depends(get_log_repo),
):
    try:
        logs = log_repo.get_operation_logs(search=search, limit=100)
        logger.info("[LOG API] Query operation logs - search=%s, count=%d", search, len(logs))
        return {"success": True, "data": logs}
    except Exception as e:
        logger.error("[LOG API] Failed to get operation logs: %s", e)
        return {"success": False, "data": [], "message": str(e)}


@router.get("/error", response_model=dict)
async def get_error_logs(
    search: Optional[str] = Query(None),
    log_repo: SystemLogRepo = Depends(get_log_repo),
):
    try:
        logs = log_repo.get_error_logs(search=search, limit=100)
        logger.info("[LOG API] Query error logs - search=%s, count=%d", search, len(logs))
        return {"success": True, "data": logs}
    except Exception as e:
        logger.error("[LOG API] Failed to get error logs: %s", e)
        return {"success": False, "data": [], "message": str(e)}


@router.get("/export", response_model=dict)
async def export_logs(
    level: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    log_repo: SystemLogRepo = Depends(get_log_repo),
):
    try:
        logs = log_repo.query(level=level, limit=1000)
        logger.info("[LOG API] Export logs - level=%s, count=%d", level, len(logs))
        return {"success": True, "data": logs}
    except Exception as e:
        logger.error("[LOG API] Failed to export logs: %s", e)
        return {"success": False, "data": [], "message": str(e)}


@router.post("", response_model=dict)
async def create_log(
    level: str = Query(...),
    action: str = Query(...),
    user: str = Query(...),
    message: str = Query(...),
    log_repo: SystemLogRepo = Depends(get_log_repo),
):
    try:
        log_repo.insert(level=level, action=action, user=user, message=message)
        logger.info("[LOG API] Created log - level=%s, action=%s, user=%s", level, action, user)
        return {"success": True, "message": "Log created successfully"}
    except Exception as e:
        logger.error("[LOG API] Failed to create log: %s", e)
        return {"success": False, "message": str(e)}
