"""Webhook 插件示例：将事件推送到外部服务。"""

import json
import logging
from typing import Dict, Any, Optional

import httpx

from plugins.base import BasePlugin, PluginConfig

plugin_config = PluginConfig(
    name="WebhookPlugin",
    version="1.0.0",
    description="将事件和传感器数据推送到指定的 Webhook URL",
    author="Heiman",
    enabled=True,
    config={
        "webhook_url": "",
        "timeout": 5,
        "secret": "",
    },
)

logger = logging.getLogger(__name__)


class WebhookPlugin(BasePlugin):
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.webhook_url = config.config.get("webhook_url", "")
        self.timeout = config.config.get("timeout", 5)
        self.secret = config.config.get("secret", "")
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def initialize(self) -> None:
        if not self.webhook_url:
            logger.warning("Webhook URL not configured, plugin will not send notifications")
        else:
            logger.info(f"WebhookPlugin initialized, URL: {self.webhook_url}")

    async def shutdown(self) -> None:
        await self.client.aclose()
        logger.info("WebhookPlugin shutdown")

    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.webhook_url:
            return None

        try:
            headers = {"Content-Type": "application/json"}
            if self.secret:
                headers["X-Webhook-Secret"] = self.secret

            payload = {
                "type": "event",
                "data": event,
            }

            response = await self.client.post(
                self.webhook_url,
                json=payload,
                headers=headers,
            )

            if response.status_code == 200:
                logger.info(f"Event sent to webhook successfully")
                return {"plugin": "WebhookPlugin", "processed": True, "status": "success"}
            else:
                logger.error(f"Webhook returned {response.status_code}: {response.text}")
                return {"plugin": "WebhookPlugin", "processed": False, "status": "failed"}

        except Exception as e:
            logger.error(f"Error sending event to webhook: {e}")
            return {"plugin": "WebhookPlugin", "processed": False, "error": str(e)}

    async def process_sensor_data(self, sensor_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.webhook_url:
            return None

        try:
            headers = {"Content-Type": "application/json"}
            if self.secret:
                headers["X-Webhook-Secret"] = self.secret

            payload = {
                "type": "sensor_data",
                "data": sensor_data,
            }

            response = await self.client.post(
                self.webhook_url,
                json=payload,
                headers=headers,
            )

            if response.status_code == 200:
                logger.info(f"Sensor data sent to webhook successfully")
                return {"plugin": "WebhookPlugin", "processed": True, "status": "success"}
            else:
                logger.error(f"Webhook returned {response.status_code}: {response.text}")
                return {"plugin": "WebhookPlugin", "processed": False, "status": "failed"}

        except Exception as e:
            logger.error(f"Error sending sensor data to webhook: {e}")
            return {"plugin": "WebhookPlugin", "processed": False, "error": str(e)}