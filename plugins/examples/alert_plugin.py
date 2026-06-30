"""告警插件示例：基于传感器阈值触发告警。"""

import logging
from typing import Dict, Any, Optional

from plugins.base import BasePlugin, PluginConfig

plugin_config = PluginConfig(
    name="AlertPlugin",
    version="1.0.0",
    description="基于传感器阈值触发告警",
    author="Heiman",
    enabled=True,
    config={
        "thresholds": {
            "temperature": {"high": 35, "low": 0},
            "humidity": {"high": 85, "low": 20},
            "co": {"high": 50},
            "smoke": {"high": 0},
            "water": {"high": 0},
        },
    },
)

logger = logging.getLogger(__name__)


class AlertPlugin(BasePlugin):
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.thresholds = config.config.get("thresholds", {})
        self.alerts = []

    async def initialize(self) -> None:
        logger.info(f"AlertPlugin initialized with thresholds: {self.thresholds}")

    async def shutdown(self) -> None:
        logger.info("AlertPlugin shutdown")

    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_type = event.get("type", "")
        if event_type == "ALERT":
            logger.warning(f"Alert triggered: {event}")
            self.alerts.append(event)
            return {"plugin": "AlertPlugin", "processed": True, "alert_count": len(self.alerts)}
        return None

    async def process_sensor_data(self, sensor_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sensor_type = sensor_data.get("type", "").lower()
        value = sensor_data.get("value")
        sensor_id = sensor_data.get("id")

        if sensor_type not in self.thresholds or value is None:
            return None

        thresholds = self.thresholds[sensor_type]
        alert = None

        if "high" in thresholds and value > thresholds["high"]:
            alert = {
                "type": "HIGH_ALERT",
                "sensor_id": sensor_id,
                "sensor_type": sensor_type,
                "value": value,
                "threshold": thresholds["high"],
                "message": f"{sensor_type} value {value} exceeds threshold {thresholds['high']}",
            }
        elif "low" in thresholds and value < thresholds["low"]:
            alert = {
                "type": "LOW_ALERT",
                "sensor_id": sensor_id,
                "sensor_type": sensor_type,
                "value": value,
                "threshold": thresholds["low"],
                "message": f"{sensor_type} value {value} below threshold {thresholds['low']}",
            }

        if alert:
            logger.warning(f"Threshold alert: {alert['message']}")
            self.alerts.append(alert)
            return {
                "plugin": "AlertPlugin",
                "processed": True,
                "alert": alert,
                "total_alerts": len(self.alerts),
            }

        return None