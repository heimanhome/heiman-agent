import logging
from typing import Optional
from fastapi import APIRouter, Query, Depends
from heiman.database.log_repo import SystemLogRepo, get_log_repo
from heiman.database.sensor_repo import SensorLogRepo
from heiman.database.event_repo import EventRepo
from heiman.manager import get_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=dict)
async def get_logs(
    level: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    user: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    log_repo: SystemLogRepo = Depends(get_log_repo),
):
    try:
        offset = (page - 1) * page_size
        logs = log_repo.query(
            level=level,
            action=action,
            user=user,
            search=search,
            limit=page_size,
            offset=offset,
        )
        total = log_repo.count(level=level, action=action, user=user, search=search)
        logger.info("[LOG API] Query logs - level=%s, action=%s, user=%s, page=%d, page_size=%d, total=%d", level, action, user, page, page_size, total)
        return {"success": True, "data": logs, "total": total, "page": page, "page_size": page_size}
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


@router.get("/device", response_model=dict)
async def get_device_logs(
    did: Optional[str] = Query(None),
    sensor_type: Optional[str] = Query(None),
    home_id: Optional[str] = Query(None),
    after: Optional[str] = Query(None),
    before: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    try:
        sensor_log_repo = SensorLogRepo()
        mgr = get_manager()
        offset = (page - 1) * page_size
        
        total = sensor_log_repo.count(
            did=did,
            sensor_type=sensor_type,
            home_id=home_id,
            after=after,
            before=before,
        )
        
        logs = sensor_log_repo.query(
            did=did,
            sensor_type=sensor_type,
            home_id=home_id,
            after=after,
            before=before,
            limit=page_size,
            offset=offset,
        )

        device_name_map = {}
        if mgr.api_client.is_authenticated:
            try:
                devices = await mgr.api_client.get_all_devices(home_id or "")
                for device in devices:
                    device_id = str(device.get("id", device.get("deviceId", "")))
                    device_name = device.get("deviceName", device.get("name", ""))
                    if device_id and device_name:
                        device_name_map[device_id] = device_name
            except Exception as e:
                logger.warning("[LOG API] Failed to get device names: %s", e)

        for log in logs:
            log_did = log.get("did", "")
            raw_properties = log.get("raw_properties", "")
            device_name = log_did
            
            if raw_properties:
                try:
                    import json
                    props = json.loads(raw_properties)
                    if isinstance(props, dict):
                        props_name = props.get("name", props.get("deviceName", ""))
                        if props_name:
                            device_name = props_name
                except (json.JSONDecodeError, TypeError):
                    pass
            
            if not device_name or device_name == log_did:
                device_name = device_name_map.get(log_did, log_did)
            
            log["device_name"] = device_name

        if search:
            search_lower = search.lower()
            logs = [
                log for log in logs
                if (search_lower in str(log.get("did", "")).lower() or
                    search_lower in str(log.get("device_name", "")).lower() or
                    search_lower in str(log.get("room_name", "")).lower() or
                    search_lower in str(log.get("sensor_type", "")).lower() or
                    search_lower in str(log.get("property_name", "")).lower())
            ]

        logger.info("[LOG API] Query device logs - did=%s, sensor_type=%s, page=%d, page_size=%d, total=%d", did, sensor_type, page, page_size, total)
        return {"success": True, "data": logs, "total": total, "page": page, "page_size": page_size}
    except Exception as e:
        logger.error("[LOG API] Failed to get device logs: %s", e)
        return {"success": False, "data": [], "message": str(e)}
