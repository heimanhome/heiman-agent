"""日志插件示例：记录所有事件和传感器数据。"""

import logging
from typing import Dict, Any, Optional

from plugins.base import BasePlugin, PluginConfig

plugin_config = PluginConfig(
    name="LogPlugin",
    version="1.0.0",
    description="记录所有事件和传感器数据到日志",
    author="Heiman",
    enabled=True,
)

logger = logging.getLogger(__name__)


class LogPlugin(BasePlugin):
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.log_level = config.config.get("log_level", "INFO")
        logger.setLevel(getattr(logging, self.log_level))

    async def initialize(self) -> None:
        logger.info(f"LogPlugin initialized with level: {self.log_level}")

    async def shutdown(self) -> None:
        logger.info("LogPlugin shutdown")

    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_type = event.get("type", "unknown")
        logger.info(f"Event: {event_type} - {event}")
        return {"plugin": "LogPlugin", "processed": True, "event_type": event_type}

    async def process_sensor_data(self, sensor_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sensor_id = sensor_data.get("id", "unknown")
        sensor_type = sensor_data.get("type", "unknown")
        value = sensor_data.get("value")
        logger.info(f"Sensor {sensor_id} ({sensor_type}): {value}")
        return {"plugin": "LogPlugin", "processed": True, "sensor_id": sensor_id}