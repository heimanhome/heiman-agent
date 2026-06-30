"""MQTT 插件：将传感器数据和事件发布到 MQTT 服务器。"""

import json
import logging
from typing import Dict, Any, Optional

import paho.mqtt.client as mqtt

from plugins.base import BasePlugin, PluginConfig

plugin_config = PluginConfig(
    name="MqttPlugin",
    version="1.0.0",
    description="将传感器数据和事件发布到 MQTT 服务器",
    author="Heiman",
    enabled=True,
    config={
        "broker": "localhost",
        "port": 1883,
        "username": "",
        "password": "",
        "topic_prefix": "heiman",
        "qos": 1,
        "retain": False,
    },
    schema={
        "broker": {"type": str, "required": True},
        "port": {"type": int, "required": True, "min": 1, "max": 65535},
        "qos": {"type": int, "min": 0, "max": 2},
        "retain": {"type": bool},
    },
    hooks=["ALERT", "SENSOR_DATA"],
)

logger = logging.getLogger(__name__)


class MqttPlugin(BasePlugin):
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.broker = config.config.get("broker", "localhost")
        self.port = config.config.get("port", 1883)
        self.username = config.config.get("username", "")
        self.password = config.config.get("password", "")
        self.topic_prefix = config.config.get("topic_prefix", "heiman")
        self.qos = config.config.get("qos", 1)
        self.retain = config.config.get("retain", False)
        self.client: Optional[mqtt.Client] = None

    async def initialize(self) -> None:
        self.client = mqtt.Client()
        if self.username:
            self.client.username_pw_set(self.username, self.password)

        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                logger.info(f"MQTT connected to {self.broker}:{self.port}")
            else:
                logger.error(f"MQTT connection failed: {rc}")

        def on_disconnect(client, userdata, rc):
            if rc != 0:
                logger.warning(f"MQTT disconnected unexpectedly, rc={rc}")

        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect

        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            logger.info(f"MqttPlugin initialized with broker: {self.broker}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    async def shutdown(self) -> None:
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MqttPlugin shutdown")

    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None

        try:
            event_type = event.get("type", "unknown")
            topic = f"{self.topic_prefix}/events/{event_type.lower()}"
            payload = json.dumps(event, ensure_ascii=False)

            result = self.client.publish(topic, payload, qos=self.qos, retain=self.retain)
            result.wait_for_publish()

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Event published to {topic}")
                return {"plugin": "MqttPlugin", "processed": True, "topic": topic}
            else:
                logger.error(f"Failed to publish event: {result.rc}")
                return {"plugin": "MqttPlugin", "processed": False, "error": f"publish failed: {result.rc}"}

        except Exception as e:
            logger.error(f"Error publishing event to MQTT: {e}")
            return {"plugin": "MqttPlugin", "processed": False, "error": str(e)}

    async def process_sensor_data(self, sensor_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None

        try:
            sensor_id = sensor_data.get("id", "unknown")
            sensor_type = sensor_data.get("type", "unknown")
            topic = f"{self.topic_prefix}/sensors/{sensor_id}/data"
            payload = json.dumps(sensor_data, ensure_ascii=False)

            result = self.client.publish(topic, payload, qos=self.qos, retain=self.retain)
            result.wait_for_publish()

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Sensor data published to {topic}")
                return {"plugin": "MqttPlugin", "processed": True, "topic": topic}
            else:
                logger.error(f"Failed to publish sensor data: {result.rc}")
                return {"plugin": "MqttPlugin", "processed": False, "error": f"publish failed: {result.rc}"}

        except Exception as e:
            logger.error(f"Error publishing sensor data to MQTT: {e}")
            return {"plugin": "MqttPlugin", "processed": False, "error": str(e)}