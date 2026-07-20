import json
import logging
import re
import threading
import uuid
from datetime import datetime
from typing import Dict, Optional, Tuple, Any

from heiman.database.event_repo import get_event_repo
from heiman.schema.sensor import SensorEvent, SensorEventType, SensorEventLevel

logger = logging.getLogger(__name__)

DEVICE_EVENT_TOPIC_PATTERN = re.compile(
    r'^/iot/app/11/[^/]+/([^/]+)/([^/]+)/event/([^/]+)$'
)

CHILD_DEVICE_EVENT_TOPIC_PATTERN = re.compile(
    r'^/iot/app/11/[^/]+/[^/]+/[^/]+/child/([^/]+)/event/([^/]+)$'
)

EVENT_TYPE_MAPPING = {
    "LowElectricityAlarm": ("low_battery", SensorEventLevel.WARNING),
    "TamperAlarm": ("tamper_alarm", SensorEventLevel.CRITICAL),
    "SmokeAlarm": ("smoke_alarm", SensorEventLevel.CRITICAL),
    "CoAlarm": ("co_alarm", SensorEventLevel.CRITICAL),
    "WaterLeak": ("water_leak", SensorEventLevel.CRITICAL),
    "DoorOpen": ("contact_alarm", SensorEventLevel.WARNING),
    "MotionDetected": ("motion_detected", SensorEventLevel.INFO),
    "TemperatureHigh": ("temperature_high", SensorEventLevel.WARNING),
    "TemperatureLow": ("temperature_low", SensorEventLevel.WARNING),
    "HumidityHigh": ("humidity_high", SensorEventLevel.WARNING),
    "HumidityLow": ("humidity_low", SensorEventLevel.WARNING),
    "Offline": ("device_offline", SensorEventLevel.WARNING),
    "Online": ("device_online", SensorEventLevel.INFO),
    "SwitchAlarm": ("switch_alarm", SensorEventLevel.CRITICAL),
}

EVENT_DESCRIPTIONS = {
    "low_battery": "设备电量低告警",
    "tamper_alarm": "设备拆动告警",
    "smoke_alarm": "烟雾告警",
    "co_alarm": "一氧化碳告警",
    "water_leak": "漏水告警",
    "contact_alarm": "门窗打开",
    "motion_detected": "移动侦测",
    "temperature_high": "温度过高告警",
    "temperature_low": "温度过低告警",
    "humidity_high": "湿度高告警",
    "humidity_low": "湿度低告警",
    "device_offline": "设备离线",
    "device_online": "设备上线",
    "switch_alarm": "开关告警",
}


class ParsedEvent:
    product_id: str
    device_id: str
    child_device_id: Optional[str]
    event_id: str
    payload: dict
    timestamp: datetime
    is_child_device: bool
    device_name: Optional[str]
    sensor_type: Optional[str]

    def __init__(self, product_id: str, device_id: str, event_id: str,
                 payload: dict, timestamp: datetime,
                 child_device_id: Optional[str] = None):
        self.product_id = product_id
        self.device_id = device_id
        self.child_device_id = child_device_id
        self.event_id = event_id
        self.payload = payload
        self.timestamp = timestamp
        self.is_child_device = child_device_id is not None
        self.device_name = None
        self.sensor_type = None


class EventProcessor:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._event_repo = get_event_repo()
        self._processing_lock = threading.Lock()
        self._processed_count = 0
        self._error_count = 0
        self._initialized = True
        logger.info("[EventProcessor] EventProcessor initialized")

    def parse_topic(self, topic: str) -> Optional[ParsedEvent]:
        child_match = CHILD_DEVICE_EVENT_TOPIC_PATTERN.match(topic)
        if child_match:
            device_id = child_match.group(1)
            event_id = child_match.group(2)
            return ParsedEvent(
                product_id="",
                device_id=device_id,
                child_device_id=device_id,
                event_id=event_id,
                payload={},
                timestamp=datetime.now(),
            )

        device_match = DEVICE_EVENT_TOPIC_PATTERN.match(topic)
        if device_match:
            product_id = device_match.group(1)
            device_id = device_match.group(2)
            event_id = device_match.group(3)
            return ParsedEvent(
                product_id=product_id,
                device_id=device_id,
                event_id=event_id,
                payload={},
                timestamp=datetime.now(),
            )

        return None

    def validate_payload(self, payload: dict) -> Tuple[bool, str]:
        if not isinstance(payload, dict):
            return False, "Payload must be a dictionary"

        if "timestamp" not in payload:
            logger.debug("[EventProcessor] Payload missing timestamp, using current time")

        if "messageId" not in payload:
            logger.debug("[EventProcessor] Payload missing messageId")

        if "data" not in payload:
            logger.debug("[EventProcessor] Payload missing data field")

        return True, ""

    def extract_timestamp(self, payload: dict) -> datetime:
        timestamp = payload.get("timestamp")
        if isinstance(timestamp, int):
            if timestamp > 1e12:
                timestamp = timestamp / 1000.0
            return datetime.fromtimestamp(timestamp)
        return datetime.now()

    def map_event_type(self, event_id: str) -> Tuple[str, SensorEventLevel]:
        mapped = EVENT_TYPE_MAPPING.get(event_id)
        if mapped:
            return mapped
        return (event_id.lower(), SensorEventLevel.INFO)

    def _determine_switch_alarm_level(self, event_id: str, payload: dict) -> SensorEventLevel:
        if event_id != "SwitchAlarm":
            return EVENT_TYPE_MAPPING.get(event_id, (event_id.lower(), SensorEventLevel.INFO))[1]

        data = payload.get("data", {})
        switch_state = data.get("SwitchState", data.get("switchState", 0))

        if switch_state == 3 or switch_state == 1:
            return SensorEventLevel.CRITICAL
        elif switch_state == 2 or switch_state == 0:
            return SensorEventLevel.INFO
        else:
            return SensorEventLevel.WARNING

    def _resolve_device_info(self, parsed: ParsedEvent) -> None:
        payload = parsed.payload or {}
        logger.info("[EventProcessor] _resolve_device_info - product_id before: %s", parsed.product_id)
        
        if isinstance(payload, dict):
            if not parsed.product_id or parsed.product_id == "heiman":
                if "productId" in payload:
                    parsed.product_id = payload["productId"]
                    logger.info("[EventProcessor] _resolve_device_info - product_id overwritten from payload: %s", parsed.product_id)
                elif "data" in payload and isinstance(payload["data"], dict):
                    data = payload["data"]
                    if "productId" in data:
                        parsed.product_id = data["productId"]
                    elif isinstance(data.get("device"), dict) and "productId" in data["device"]:
                        parsed.product_id = data["device"]["productId"]
                elif isinstance(payload.get("device"), dict) and "productId" in payload["device"]:
                    parsed.product_id = payload["device"]["productId"]

        if not parsed.product_id:
            parsed.product_id = "heiman"

        try:
            from heiman.manager import get_manager
            mgr = get_manager()
            devices = mgr.adapter.get_connected_devices()
            
            target_did = parsed.child_device_id if parsed.is_child_device else parsed.device_id
            if target_did in devices:
                device = devices[target_did]
                parsed.device_name = device.name
                parsed.sensor_type = device.device_type
            else:
                try:
                    from heiman.dependencies import get_collector
                    collector = get_collector()
                    device_data = collector.collect(target_did, drain=False)
                    if device_data and device_data.meta:
                        parsed.device_name = device_data.meta.name
                        parsed.sensor_type = device_data.meta.device_type
                except Exception as e:
                    logger.debug("[EventProcessor] Failed to get device from collector: %s", e)
            
            if not parsed.device_name or parsed.device_name == target_did or parsed.device_name.startswith("Device "):
                try:
                    from heiman.database.connector import get_db_connector
                    from heiman.database.product_repo import ProductRepo
                    db = get_db_connector()
                    repo = ProductRepo(db)
                    
                    cursor = db.get_connection().cursor()
                    cursor.execute(
                        "SELECT name FROM sensor_logs WHERE did = ? AND name IS NOT NULL AND name != '' AND name != did ORDER BY id DESC LIMIT 1",
                        (target_did,)
                    )
                    row = cursor.fetchone()
                    if row and row[0]:
                        parsed.device_name = row[0]
                    else:
                        if parsed.product_id and parsed.product_id != "heiman":
                            product_info = repo.get_product(parsed.product_id)
                            if product_info:
                                parsed.device_name = product_info.get("name", target_did)
                except Exception as e:
                    logger.debug("[EventProcessor] Failed to get device name from database: %s", e)
            logger.info("[EventProcessor] _resolve_device_info - product_id after: %s", parsed.product_id)
        except Exception as e:
            logger.debug("[EventProcessor] Failed to resolve device info: %s", e)

    def build_sensor_event(self, parsed: ParsedEvent) -> SensorEvent:
        event_type_str, base_level = self.map_event_type(parsed.event_id)
        
        if event_type_str == "switch_alarm":
            level = self._determine_switch_alarm_level(parsed.event_id, parsed.payload)
            
            sensor_type = parsed.sensor_type or ""
            data = parsed.payload.get("data", {})
            switch_state = data.get("SwitchState", data.get("switchState", 0))
            
            device_name = parsed.device_name or ""
            device_name_lower = device_name.lower()
            
            is_contact = False
            is_plug = False
            
            if parsed.product_id:
                try:
                    from heiman.database.connector import get_db_connector
                    from heiman.database.product_repo import ProductRepo
                    db = get_db_connector()
                    repo = ProductRepo(db)
                    product_info = repo.get_product(parsed.product_id)
                    if product_info:
                        db_product_name = product_info.get("name", "")
                        if "门磁" in db_product_name or "门窗" in db_product_name or "contact" in db_product_name.lower():
                            is_contact = True
                        elif "插座" in db_product_name or "plug" in db_product_name.lower():
                            is_plug = True
                except Exception as e:
                    logger.debug("[EventProcessor] Failed to get product info: %s", e)
            
            if not is_contact and not is_plug:
                if "门磁" in device_name or "门窗" in device_name:
                    is_contact = True
                elif "插座" in device_name:
                    is_plug = True
                elif "contact" in sensor_type.lower():
                    is_contact = True
                elif "plug" in sensor_type.lower():
                    is_plug = True
            
            if is_contact:
                if switch_state == 3 or switch_state == 1:
                    description = "门窗打开"
                elif switch_state == 2 or switch_state == 0:
                    description = "门窗关闭"
                else:
                    description = "门窗状态变更"
            elif is_plug:
                if switch_state == 3 or switch_state == 1:
                    description = "插座开启"
                elif switch_state == 2 or switch_state == 0:
                    description = "插座关闭"
                else:
                    description = "插座状态变更"
            elif sensor_type == "motion" or sensor_type == "pir":
                if switch_state == 2:
                    description = "检测到移动"
                elif switch_state == 3:
                    description = "移动结束"
                else:
                    description = "移动状态变更"
            else:
                description = EVENT_DESCRIPTIONS.get(event_type_str, f"事件: {parsed.event_id}")
        else:
            level = base_level
            description = EVENT_DESCRIPTIONS.get(event_type_str, f"事件: {parsed.event_id}")

        try:
            event_type_enum = SensorEventType(event_type_str)
        except ValueError:
            try:
                enum_name = event_type_str.upper()
                event_type_enum = SensorEventType[enum_name]
            except (KeyError, AttributeError):
                event_type_enum = SensorEventType.ALARM

        target_device_id = parsed.child_device_id if parsed.is_child_device else parsed.device_id
        
        device_name = parsed.device_name if parsed.device_name else target_device_id

        return SensorEvent(
            event_id=f"{target_device_id}_{parsed.event_id}_{int(parsed.timestamp.timestamp() * 1000)}",
            event_type=event_type_enum,
            level=level,
            did=target_device_id,
            device_name=device_name,
            room_name=None,
            home_id=None,
            product_id=parsed.product_id,
            child_device_id=parsed.child_device_id,
            description=description,
            raw_data={
                "productId": parsed.product_id,
                "deviceId": parsed.device_id,
                "childDeviceId": parsed.child_device_id,
                "eventId": parsed.event_id,
                "payload": parsed.payload,
                "sensorType": parsed.sensor_type,
                "deviceName": device_name,
            },
            timestamp=parsed.timestamp,
            acknowledged=False,
        )

    async def process_event(self, topic: str, payload: dict) -> bool:
        with self._processing_lock:
            try:
                logger.info("[EventProcessor] Processing event from topic: %s", topic)

                parsed = self.parse_topic(topic)
                if not parsed:
                    logger.error("[EventProcessor] Failed to parse topic: %s", topic)
                    self._error_count += 1
                    return False

                valid, error_msg = self.validate_payload(payload)
                if not valid:
                    logger.error("[EventProcessor] Invalid payload: %s", error_msg)
                    self._error_count += 1
                    return False

                parsed.payload = payload
                parsed.timestamp = self.extract_timestamp(payload)

                product_id = parsed.product_id
                logger.info("[EventProcessor] product_id from topic: %s", product_id)
                
                if not product_id or product_id == "heiman":
                    payload_product_id = payload.get("productId", "")
                    if payload_product_id and payload_product_id != "heiman":
                        product_id = payload_product_id
                        logger.info("[EventProcessor] product_id from payload: %s", product_id)
                    else:
                        try:
                            from heiman.database.connector import get_db_connector
                            from heiman.database.product_repo import ProductRepo
                            db = get_db_connector()
                            repo = ProductRepo(db)
                            with db.get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "SELECT DISTINCT product_id FROM sensor_logs WHERE did = ? AND product_id IS NOT NULL AND product_id != '' ORDER BY id DESC",
                                    (parsed.device_id,)
                                )
                                rows = cursor.fetchall()
                                
                                fallback_product_id = None
                                for row in rows:
                                    pid = str(row[0])
                                    if pid:
                                        if fallback_product_id is None:
                                            fallback_product_id = pid
                                        product_info = repo.get_product(pid)
                                        if product_info:
                                            classified_name = product_info.get("classified_name", "")
                                            product_name = product_info.get("name", "")
                                            if "网关" not in classified_name and "网关" not in product_name:
                                                product_id = pid
                                                logger.info("[EventProcessor] Resolved product_id from sensor_logs (non-gateway): %s", product_id)
                                                break
                                
                                if not product_id and fallback_product_id:
                                    product_id = fallback_product_id
                                    logger.info("[EventProcessor] Resolved product_id from sensor_logs (fallback): %s", product_id)
                        except Exception as e:
                            logger.error("[EventProcessor] Failed to resolve product_id from sensor_logs: %s", e)
                parsed.product_id = product_id
                logger.info("[EventProcessor] Final product_id: %s", parsed.product_id)

                self._resolve_device_info(parsed)

                sensor_event = self.build_sensor_event(parsed)

                self._event_repo.insert(sensor_event)

                await self.publish_to_event_bus(sensor_event)

                self._processed_count += 1
                logger.info(
                    "[EventProcessor] Event processed successfully - event_id=%s, type=%s, level=%s, is_child=%s",
                    sensor_event.event_id,
                    sensor_event.event_type.value,
                    sensor_event.level.value,
                    parsed.is_child_device,
                )
                return True

            except Exception as e:
                logger.error(
                    "[EventProcessor] Error processing event from topic %s: %s",
                    topic,
                    str(e),
                    exc_info=True,
                )
                self._error_count += 1
                return False

    async def publish_to_event_bus(self, event: SensorEvent):
        try:
            from heiman.service.event_bus import get_event_bus

            bus = get_event_bus()
            await bus.publish({
                "event": "device_event",
                "id": event.event_id,
                "data": {
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "level": event.level.value,
                    "did": event.did,
                    "device_name": event.device_name,
                    "description": event.description,
                    "timestamp": event.timestamp.isoformat(),
                    "acknowledged": event.acknowledged,
                    "raw_data": event.raw_data,
                },
            })
            logger.debug("[EventProcessor] Event published to event bus: %s", event.event_id)
        except Exception as e:
            logger.warning("[EventProcessor] Failed to publish to event bus: %s", e)

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "processed_count": self._processed_count,
            "error_count": self._error_count,
        }


def get_event_processor() -> EventProcessor:
    return EventProcessor()