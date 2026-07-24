import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


logger = logging.getLogger(__name__)


class CollectorType(str, Enum):
    SENSOR = "sensor"
    CAMERA = "camera"
    MICROPHONE = "microphone"
    BLUETOOTH = "bluetooth"
    MQTT = "mqtt"


@dataclass
class CollectorConfig:
    type: CollectorType
    name: str
    enabled: bool = True
    interval: float = 1.0
    config: Dict[str, Any] = field(default_factory=dict)


class BaseCollector:
    def __init__(self, config: CollectorConfig):
        self.config = config
        self._running = False
        self._callback = None

    async def start(self):
        self._running = True
        logger.info(f"Started collector: {self.config.name}")

    async def stop(self):
        self._running = False
        logger.info(f"Stopped collector: {self.config.name}")

    def set_callback(self, callback):
        self._callback = callback

    async def collect(self) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


class SensorCollector(BaseCollector):
    async def start(self):
        await super().start()
        asyncio.create_task(self._collection_loop())

    async def _collection_loop(self):
        while self._running:
            data = await self._fetch_sensor_data()
            if data and self._callback:
                await self._callback(data)
            await asyncio.sleep(self.config.interval)

    async def _fetch_sensor_data(self) -> Optional[Dict[str, Any]]:
        try:
            from heiman.manager import get_manager
            mgr = get_manager()
            # 使用已有的 query 方法获取最近10条传感器日志
            sensors = mgr.sensor_log_repo.query(limit=10)
            if sensors:
                return {
                    "type": "sensor_data",
                    "sensors": [s.to_dict() if hasattr(s, 'to_dict') else dict(s) for s in sensors],
                    "timestamp": asyncio.get_event_loop().time(),
                }
        except Exception as e:
            logger.error(f"Sensor collection failed: {e}")
        return None


class MockCameraCollector(BaseCollector):
    async def start(self):
        await super().start()
        asyncio.create_task(self._collection_loop())

    async def _collection_loop(self):
        while self._running:
            data = await self._generate_mock_data()
            if data and self._callback:
                await self._callback(data)
            await asyncio.sleep(self.config.interval * 5)

    async def _generate_mock_data(self) -> Optional[Dict[str, Any]]:
        return {
            "type": "camera_event",
            "location": "living_room",
            "motion_detected": True,
            "person_detected": True,
            "timestamp": asyncio.get_event_loop().time(),
            "confidence": 0.85,
        }


class MockMicrophoneCollector(BaseCollector):
    async def start(self):
        await super().start()
        asyncio.create_task(self._collection_loop())

    async def _collection_loop(self):
        while self._running:
            data = await self._generate_mock_data()
            if data and self._callback:
                await self._callback(data)
            await asyncio.sleep(self.config.interval * 3)

    async def _generate_mock_data(self) -> Optional[Dict[str, Any]]:
        return {
            "type": "audio_event",
            "location": "living_room",
            "sound_detected": True,
            "speech_detected": True,
            "content": "回家了",
            "timestamp": asyncio.get_event_loop().time(),
            "confidence": 0.7,
        }


class PerceptionCollector:
    def __init__(self):
        self._collectors: Dict[str, BaseCollector] = {}
        self._engine = None

    def set_engine(self, engine):
        self._engine = engine

    def add_collector(self, collector: BaseCollector):
        self._collectors[collector.config.name] = collector
        collector.set_callback(self._on_data)
        logger.info(f"Added collector: {collector.config.name}")

    async def start_all(self):
        for collector in self._collectors.values():
            if collector.config.enabled:
                await collector.start()

    async def stop_all(self):
        for collector in self._collectors.values():
            await collector.stop()

    async def _on_data(self, data: Dict[str, Any]):
        if self._engine:
            from heiman.perception.engine import PerceptionEvent, PerceptionType

            event_type_map = {
                "sensor_data": PerceptionType.ENVIRONMENT,
                "camera_event": PerceptionType.MOTION,
                "audio_event": PerceptionType.SPEECH,
            }

            event = PerceptionEvent(
                event_id=f"evt-{int(asyncio.get_event_loop().time())}-{id(data)}",
                type=event_type_map.get(data.get("type"), PerceptionType.ACTIVITY),
                source=data.get("location", "unknown"),
                location=data.get("location"),
                confidence=data.get("confidence", 0.0),
                timestamp=data.get("timestamp", asyncio.get_event_loop().time()),
                data=data,
            )

            await self._engine.submit_event(event)

    def get_collector(self, name: str) -> Optional[BaseCollector]:
        return self._collectors.get(name)

    def list_collectors(self) -> List[Dict]:
        return [
            {
                "name": c.config.name,
                "type": c.config.type.value,
                "enabled": c.config.enabled,
            }
            for c in self._collectors.values()
        ]