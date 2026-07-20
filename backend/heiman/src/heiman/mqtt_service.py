import asyncio
import json
import logging
import ssl as ssl_module
from typing import Callable, Dict, List, Optional

from heiman.config import get_settings
from heimanhome_mqtt.client import HeimanMqttClient
from heimanhome_mqtt.auth import generate_third_party_auth

logger = logging.getLogger(__name__)


class MqttService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._mqtt_broker = ""
        self._mqtt_port = 1884
        self._mqtt_ssl_enabled = True
        self._secure_id = ""
        self._secure_key = ""
        self._client_id = ""
        self._username = ""
        self._password = ""
        self._user_id = ""
        self._access_token = ""

        self._client: HeimanMqttClient | None = None
        self._connected = False
        self._connecting = False
        self._should_reconnect = True
        self._reconnect_attempts = 0
        self._reconnecting = False

        self._message_callbacks: List[Callable[[str, Dict], None]] = []
        self._device_callbacks: List[Callable[[str, Dict], None]] = []
        self._event_callbacks: List[Callable[[str, str, Dict], None]] = []
        self._raw_message_callbacks: List[Callable[[str, Dict], None]] = []

        self._initialized = True
        logger.info("[MQTT] MqttService initialized")

    def _load_settings(self):
        settings = get_settings()
        self._mqtt_broker = settings.heiman.mqtt_broker
        self._mqtt_port = settings.heiman.mqtt_port
        self._mqtt_ssl_enabled = settings.heiman.mqtt_ssl_enabled
        self._secure_id = settings.heiman.secure_id
        self._secure_key = settings.heiman.secure_key
        logger.info(
            "[MQTT] Settings loaded - broker=%s:%d, secure_id=%s, secure_key_configured=%s",
            self._mqtt_broker,
            self._mqtt_port,
            self._secure_id,
            "yes" if self._secure_key else "no",
        )

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    def update_token(self, access_token: str) -> None:
        """Update access token without disconnecting.
        
        The MQTT connection only validates token during connect,
        so we just update the stored token for future reconnects.
        """
        old_len = len(self._access_token) if self._access_token else 0
        new_len = len(access_token) if access_token else 0
        self._access_token = access_token
        
        if self._client and hasattr(self._client, 'update_access_token'):
            self._client.update_access_token(access_token)
        
        logger.info(
            "[MQTT] Access token updated - old_len=%d, new_len=%d",
            old_len,
            new_len,
        )

    async def connect(self, access_token: str, user_id: str) -> bool:
        if self._connected:
            logger.info("[MQTT] Already connected")
            return True

        if self._connecting:
            logger.info("[MQTT] Already connecting, waiting for existing connection")
            for _ in range(20):
                await asyncio.sleep(0.5)
                if self._connected:
                    return True
                if not self._connecting:
                    break
            logger.warning("[MQTT] Connection attempt timed out, retrying")

        self._connecting = True
        self._access_token = access_token
        self._user_id = user_id

        try:
            self._load_settings()

            logger.info(
                "[MQTT] Connect request received - access_token_length=%d, user_id=%s, broker=%s:%d",
                len(access_token) if access_token else 0,
                user_id,
                self._mqtt_broker,
                self._mqtt_port,
            )

            if not self._secure_id or not self._secure_key:
                logger.warning(
                    "[MQTT] secure_id or secure_key not configured, skipping MQTT connection"
                )
                self._connecting = False
                return False

            logger.info(
                "[MQTT] Creating HeimanMqttClient - broker=%s, port=%d, ssl=%s",
                self._mqtt_broker,
                self._mqtt_port,
                self._mqtt_ssl_enabled,
            )

            # 断开旧 client,避免两个 client 用同一个 client_id 互相踢
            if self._client is not None:
                try:
                    await self._client.disconnect()
                    logger.info("[MQTT] Disconnected old client before creating new one")
                except Exception as e:
                    logger.warning("[MQTT] Error disconnecting old client: %s", e)
                self._client = None

            self._client = HeimanMqttClient(
                access_token=access_token,
                user_id=user_id,
                secure_id=self._secure_id,
                secure_key=self._secure_key,
                mqtt_broker=self._mqtt_broker,
                mqtt_port=self._mqtt_port,
                ssl_enabled=self._mqtt_ssl_enabled,
                auto_reconnect=False,
            )

            app_topic_wildcard = f"/iot/app/11/{user_id}/#"
            self._client.add_topic_callback(app_topic_wildcard, self._on_raw_message)
            logger.info("[MQTT] Registered raw message callback for app topic: %s", app_topic_wildcard)

            logger.info("[MQTT] Initiating connection...")
            logger.info(
                "[MQTT] Auth params - client_id=%s, username=%s, password=%s",
                self._client.client_id,
                self._client.username,
                self._client._password[:8] + "..." if self._client._password else "None",
            )
            
            try:
                connected = await asyncio.wait_for(self._client.connect(), timeout=30.0)
            except asyncio.TimeoutError:
                logger.error("[MQTT] Connection timeout after 30 seconds - possible network issue or SSL handshake failure")
                self._connecting = False
                self._cleanup()
                return False
            except Exception as e:
                logger.error("[MQTT] Connection exception: %s", str(e))
                self._connecting = False
                self._cleanup()
                return False

            if connected:
                self._connected = True
                self._reconnect_attempts = 0
                logger.info(
                    "[MQTT] Connection established successfully - user_id=%s, client_id=%s",
                    user_id,
                    self._client.client_id,
                )

                subscribed_topics = getattr(self._client, '_subscribed_topics', set())
                logger.info("[MQTT] Current subscribed topics: %s", subscribed_topics)

                app_topic = f"/iot/app/11/{user_id}/#"
                if app_topic not in subscribed_topics:
                    self._client.subscribe(app_topic)
                    logger.info("[MQTT] Subscribed to app topic: %s", app_topic)
                else:
                    logger.info("[MQTT] App topic already subscribed: %s", app_topic)

                await self.start_connection_monitor()

                return True
            else:
                logger.error("[MQTT] Connection failed: HeimanMqttClient.connect() returned False")
                self._connecting = False
                return False

        except Exception as e:
            logger.error("[MQTT] Connection failed: %s", e)
            self._connecting = False
            self._cleanup()
            return False

    async def disconnect(self) -> None:
        logger.info("[MQTT] Disconnecting")
        self._should_reconnect = False

        if self._client:
            try:
                await self._client.disconnect()
                logger.info("[MQTT] Disconnected")
            except Exception as e:
                logger.error("[MQTT] Error during disconnect: %s", e)

        self._cleanup()
        logger.info("[MQTT] Cleanup completed")

    def _cleanup(self):
        self._connected = False
        self._connecting = False
        if self._client is not None:
            try:
                # 同步 disconnect,paho-mqtt 内部是线程安全的
                asyncio.ensure_future(self._client.disconnect())
            except Exception:
                pass
        self._client = None

    def _on_device_update(self, device_id: str, data: dict, topic: str = ""):
        try:
            properties = data.get("properties", {})
            logger.info("[MQTT] Device update for %s: %s", device_id, properties)

            for callback in self._device_callbacks:
                try:
                    callback(device_id, data, topic)
                except Exception as e:
                    logger.error("[MQTT] Error in device callback: %s", e)
        except Exception as e:
            logger.error("[MQTT] Error handling device update: %s", e)

    def _on_event_received(self, device_id: str, event_type: str, payload: dict, topic: str = ""):
        try:
            logger.info("[MQTT] Event from device %s: %s", device_id, event_type)

            for callback in self._event_callbacks:
                try:
                    callback(device_id, event_type, payload, topic)
                except Exception as e:
                    logger.error("[MQTT] Error in event callback: %s", e)
        except Exception as e:
            logger.error("[MQTT] Error handling event: %s", e)

    def _on_disconnect(self, rc: int):
        logger.warning("[MQTT] Disconnected with rc=%d", rc)
        self._connected = False

        if self._should_reconnect and self._access_token and self._user_id:
            if self._reconnecting:
                logger.info("[MQTT] Reconnection already in progress, skipping")
                return
            logger.info("[MQTT] Scheduling reconnection attempt")
            asyncio.create_task(self._reconnect_with_backoff())

    async def _reconnect_with_backoff(self):
        if not self._should_reconnect or not self._access_token:
            return

        if self._reconnecting:
            logger.info("[MQTT] Reconnection already in progress, skipping")
            return
        self._reconnecting = True
        
        backoff_delay = 5
        max_backoff = 60

        try:
            while self._should_reconnect and not self._connected:
                logger.info("[MQTT] Attempting reconnection after %d seconds delay", backoff_delay)

                try:
                    await asyncio.sleep(backoff_delay)

                    if not self._should_reconnect:
                        return

                    logger.info("[MQTT] Trying to reconnect with existing token")
                    self._cleanup()
                    success = await self.connect(self._access_token, self._user_id)

                    if success:
                        logger.info("[MQTT] Reconnection successful")
                        return
                    else:
                        logger.warning("[MQTT] Reconnection attempt failed")

                except Exception as e:
                    logger.error("[MQTT] Reconnection error: %s", e)

                backoff_delay = min(backoff_delay * 2, max_backoff)

            logger.info("[MQTT] Reconnection loop exited")
        finally:
            self._reconnecting = False

    async def start_connection_monitor(self):
        if hasattr(self, '_monitor_task') and not self._monitor_task.done():
            return
        
        async def monitor():
            while self._should_reconnect:
                await asyncio.sleep(10)
                
                if self._connected and self._client:
                    if not self._client.is_connected:
                        logger.warning("[MQTT] Connection monitor detected disconnection")
                        self._on_disconnect(0)
                elif self._should_reconnect and self._access_token and self._user_id:
                    logger.info("[MQTT] Connection monitor: not connected, triggering reconnection")
                    asyncio.create_task(self._reconnect_with_backoff())
        
        self._monitor_task = asyncio.create_task(monitor())
        logger.info("[MQTT] Connection monitor started")

    def _on_raw_message(self, topic: str, payload: dict):
        try:
            logger.info("[MQTT] Raw message received:")
            logger.info("[MQTT]   Topic: %s", topic)
            logger.info("[MQTT]   Payload: %s", json.dumps(payload, indent=2, ensure_ascii=False))

            device_id = self._extract_device_id(topic)
            if device_id:
                self._process_device_message(device_id, topic, payload)

            for callback in self._raw_message_callbacks:
                try:
                    callback(topic, payload)
                except Exception as e:
                    logger.error("[MQTT] Error in raw message callback: %s", e)
        except Exception as e:
            logger.error("[MQTT] Error handling raw message: %s", e)

    def _extract_device_id(self, topic: str) -> Optional[str]:
        parts = topic.strip('/').split('/')
        for i, part in enumerate(parts):
            if part == 'device' and i + 1 < len(parts):
                return parts[i + 1]
            if part == 'child' and i + 1 < len(parts):
                return parts[i + 1]
        return None

    def _process_device_message(self, device_id: str, topic: str, payload: dict):
        try:
            parts = topic.strip('/').split('/')
            
            if 'properties' in parts and 'report' in parts:
                self._on_device_update(device_id, payload, topic)
            elif 'event' in parts:
                event_index = parts.index('event')
                event_type = parts[event_index + 1] if event_index + 1 < len(parts) else 'unknown'
                self._on_event_received(device_id, event_type, payload, topic)
            else:
                logger.debug("[MQTT] Unknown message type for device %s: %s", device_id, topic)
        except Exception as e:
            logger.error("[MQTT] Error processing device message: %s", e)

    def register_message_callback(self, callback: Callable[[str, Dict], None]):
        self._message_callbacks.append(callback)
        logger.debug("[MQTT] Registered message callback")

    def unregister_message_callback(self, callback: Callable[[str, Dict], None]):
        if callback in self._message_callbacks:
            self._message_callbacks.remove(callback)
            logger.debug("[MQTT] Unregistered message callback")

    def register_device_callback(self, callback: Callable[[str, Dict], None]):
        self._device_callbacks.append(callback)
        logger.debug("[MQTT] Registered device callback")

    def unregister_device_callback(self, callback: Callable[[str, Dict], None]):
        if callback in self._device_callbacks:
            self._device_callbacks.remove(callback)
            logger.debug("[MQTT] Unregistered device callback")

    def register_event_callback(self, callback: Callable[[str, str, Dict], None]):
        self._event_callbacks.append(callback)
        logger.debug("[MQTT] Registered event callback")

    def unregister_event_callback(self, callback: Callable[[str, str, Dict], None]):
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)
            logger.debug("[MQTT] Unregistered event callback")

    def register_raw_message_callback(self, callback: Callable[[str, Dict], None]):
        self._raw_message_callbacks.append(callback)
        logger.debug("[MQTT] Registered raw message callback")

    def unregister_raw_message_callback(self, callback: Callable[[str, Dict], None]):
        if callback in self._raw_message_callbacks:
            self._raw_message_callbacks.remove(callback)
            logger.debug("[MQTT] Unregistered raw message callback")

    async def publish(self, topic: str, payload: Dict):
        if not self._connected or not self._client:
            raise Exception("MQTT not connected")

        try:
            await self._client.publish(topic, payload)
            logger.debug("[MQTT] Published to %s: %s", topic, json.dumps(payload)[:200])
        except Exception as e:
            logger.error("[MQTT] Failed to publish: %s", e)
            raise

    async def write_device_property(self, pid: str, device_id: str, properties: Dict):
        topic = f"/{pid}/{device_id}/properties/write"
        payload = {
            "messageId": f"msg_{int(asyncio.get_event_loop().time() * 1000)}",
            "deviceId": device_id,
            "properties": properties,
        }
        await self.publish(topic, payload)
        logger.info("[MQTT] Write property to device %s: %s", device_id, properties)


def get_mqtt_service() -> MqttService:
    return MqttService()