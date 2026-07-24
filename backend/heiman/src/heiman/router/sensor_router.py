from typing import Annotated
import logging

from fastapi import APIRouter, Depends, Query, Header

from heiman.classifier.event_classifier import EventClassifier
from heiman.collector.sensor_collector import SensorCollector
from heiman.database.event_repo import EventRepo
from heiman.database.sensor_repo import SensorLogRepo
from heiman.dependencies import (
    get_collector,
    get_event_classifier,
    get_event_repo,
    get_sensor_log_repo,
)
from heiman.schema.sensor import SensorData, SensorStatus, SensorType

router = APIRouter(prefix="/sensors", tags=["sensors"])
logger = logging.getLogger(__name__)


@router.get("", response_model=dict)
async def get_sensors(
    sensor_type: Annotated[SensorType | None, Query()] = None,
    status: Annotated[SensorStatus | None, Query()] = None,
    home_id: Annotated[str | None, Query()] = None,
    collector: SensorCollector = Depends(get_collector),
    authorization: str | None = Header(None),
):
    logger.debug("get_sensors called: type=%s, status=%s, home_id=%s", sensor_type, status, home_id)
    try:
        from heiman.manager import get_manager
        mgr = get_manager()

        if mgr.api_client.is_authenticated:
            logger.info("Fetching sensors from API client (authenticated)")
            sensor_data_list = await mgr.api_client.get_sensor_data(home_id)
            logger.info("API returned %d sensors", len(sensor_data_list))
        else:
            logger.info("Fetching sensors from local collector (offline mode)")
            sensor_data_list = collector.get_sensor_data_list()
            logger.info("Collector returned %d sensors", len(sensor_data_list))

        if sensor_type:
            sensor_data_list = [s for s in sensor_data_list if s.sensor_type == sensor_type]
            logger.debug("Filtered by type=%s: %d sensors", sensor_type, len(sensor_data_list))

        if status:
            sensor_data_list = [s for s in sensor_data_list if s.status == status]
            logger.debug("Filtered by status=%s: %d sensors", status, len(sensor_data_list))

        for sensor_data in sensor_data_list:
            timestamp_str = sensor_data.timestamp.isoformat()
            if not mgr.sensor_log_repo.check_exists(sensor_data.did, timestamp_str):
                mgr.sensor_log_repo.insert(sensor_data)

        logger.info("get_sensors success: returning %d sensors", len(sensor_data_list))
        return {"success": True, "data": sensor_data_list}
    except Exception as e:
        logger.error("Failed to get sensors: %s", e, exc_info=True)
        return {"success": False, "data": [], "message": str(e)}


@router.get("/{did}", response_model=dict)
async def get_sensor(
    did: str,
    home_id: Annotated[str | None, Query()] = None,
    collector: SensorCollector = Depends(get_collector),
):
    try:
        from heiman.manager import get_manager
        mgr = get_manager()

        sensors = await mgr.api_client.get_sensor_data(home_id)
        sensor = next((s for s in sensors if s.did == did), None)
        if sensor:
            return {"success": True, "data": sensor}

        device_data = collector.collect(did, drain=False)
        if device_data and device_data.sensor_data:
            return {"success": True, "data": device_data.sensor_data}

        return {"success": False, "message": "Sensor not found"}
    except Exception as e:
        logger.error("Failed to get sensor %s: %s", did, e)
        return {"success": False, "message": str(e)}


@router.post("/data", response_model=dict)
async def push_sensor_data(
    sensor_data: SensorData,
    event_classifier: EventClassifier = Depends(get_event_classifier),
    event_repo: EventRepo = Depends(get_event_repo),
):
    try:
        events = event_classifier.classify(sensor_data)
        for event in events:
            event_repo.insert(event)

        return {"success": True, "data": sensor_data}
    except Exception as e:
        logger.error("Failed to push sensor data: %s", e)
        return {"success": False, "message": str(e)}


@router.get("/{did}/history", response_model=dict)
async def get_sensor_history(
    did: str,
    start_time: Annotated[str, Query()] = None,
    end_time: Annotated[str, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    sensor_log_repo: SensorLogRepo = Depends(get_sensor_log_repo),
):
    try:
        data = sensor_log_repo.query(did=did, after=start_time, before=end_time, limit=limit)
        return {"success": True, "data": data}
    except Exception as e:
        logger.error("Failed to get sensor history: %s", e)
        return {"success": False, "data": [], "message": str(e)}