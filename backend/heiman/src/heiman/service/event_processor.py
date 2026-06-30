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
    r'^/([^/]+)/([^/]+)/event/([^/]+)$'
)

CHILD_DEVICE_EVENT_TOPIC_PATTERN = re.compile(
    r'^/([^/]+)/([^/]+)/child/([^/]+)/event/([^/]+)$'
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
}


class ParsedEvent:
    product_id: str
    device_id: str
    child_device_id: Optional[str]
    event_id: str
    payload: dict
    timestamp: datetime
    is_child_device: bool

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
            product_id = child_match.group(1)
            device_id = child_match.group(2)
            child_device_id = child_match.group(3)
            event_id = child_match.group(4)
            return ParsedEvent(
                product_id=product_id,
                device_id=device_id,
                child_device_id=child_device_id,
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
            logger.warning("[EventProcessor] Payload missing timestamp, using current time")

        if "messageId" not in payload:
            logger.warning("[EventProcessor] Payload missing messageId")

        if "data" not in payload:
            logger.warning("[EventProcessor] Payload missing data field")

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

    def build_sensor_event(self, parsed: ParsedEvent) -> SensorEvent:
        event_type_str, level = self.map_event_type(parsed.event_id)
        description = EVENT_DESCRIPTIONS.get(event_type_str, f"事件: {parsed.event_id}")

        try:
            event_type_enum = SensorEventType(event_type_str)
        except ValueError:
            event_type_enum = SensorEventType.SMOKE_ALARM

        target_device_id = parsed.child_device_id if parsed.is_child_device else parsed.device_id

        return SensorEvent(
            event_id=f"{target_device_id}_{parsed.event_id}_{int(parsed.timestamp.timestamp() * 1000)}",
            event_type=event_type_enum,
            level=level,
            did=target_device_id,
            device_name=target_device_id,
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
            },
            timestamp=parsed.timestamp,
            acknowledged=False,
        )

    def process_event(self, topic: str, payload: dict) -> bool:
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

                sensor_event = self.build_sensor_event(parsed)

                self._event_repo.insert(sensor_event)

                self.publish_to_event_bus(sensor_event)

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

    def publish_to_event_bus(self, event: SensorEvent):
        try:
            from heiman.service.event_bus import get_event_bus

            bus = get_event_bus()
            bus.publish({
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