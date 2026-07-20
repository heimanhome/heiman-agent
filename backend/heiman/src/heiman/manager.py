import logging
import asyncio
import time
from uuid import uuid4
from datetime import datetime

from heiman.adapter.sensor_adapter import SensorDeviceAdapter
from heiman.classifier.event_classifier import EventClassifier
from heiman.collector.sensor_collector import SensorCollector
from heiman.client.heiman_api_client import HeimanApiClient
from heiman.config import get_settings
from heiman.database.event_repo import EventRepo
from heiman.database.person_repo import PersonRepo
from heiman.database.rule_repo import RuleRepo
from heiman.database.sensor_repo import SensorLogRepo
from heiman.dependencies import (
    set_collector,
    set_event_classifier,
    set_rule_engine,
    set_sensor_log_repo,
    set_event_repo,
    set_rule_repo,
    set_event_processor,
)
from heiman.home_profile.service import HomeProfileService
from heiman.rule.rule_engine import RuleEngine
from heiman.schema.sensor import SensorEvent, SensorEventLevel, SensorEventType
from heiman.service.event_processor import EventProcessor
from heiman.service.person_service import PersonService
from heiman.service.task_service import TaskService

logger = logging.getLogger(__name__)

LOGIN_MAX_RETRIES = 3
LOGIN_TIMEOUT_SECONDS = 10.0
LOGIN_RETRY_DELAY = 5
SYNC_TIMEOUT_SECONDS = 15.0


class Manager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        pass

    async def initialize(self):
        if getattr(self, "_initialized", False):
            logger.debug("Manager already initialized, skipping")
            return

        logger.info("Manager initialization started")
        self._event_loop = asyncio.get_running_loop()
        settings = get_settings()

        self._api_client = await self._initialize_api_client()
        self._offline_mode = not self._api_client.is_authenticated

        if self._offline_mode:
            logger.warning("Running in OFFLINE mode - sensor data will not be available")
        else:
            logger.info("API client authenticated successfully")

        self._adapter = SensorDeviceAdapter(self._api_client)

        if not self._offline_mode:
            try:
                await asyncio.wait_for(
                    self._adapter.sync_devices(),
                    timeout=SYNC_TIMEOUT_SECONDS,
                )
                await asyncio.wait_for(
                    self._adapter.refresh_sensor_data(),
                    timeout=SYNC_TIMEOUT_SECONDS,
                )
                logger.info("Device sync completed successfully")
            except asyncio.TimeoutError:
                logger.warning("Device sync timed out, continuing with empty device list")
            except Exception as e:
                logger.warning("Device sync failed: %s, continuing in limited mode", e)

        self._collector = SensorCollector([self._adapter])
        self._event_classifier = EventClassifier()
        self._rule_engine = RuleEngine()
        self._sensor_log_repo = SensorLogRepo()
        self._event_repo = EventRepo()
        self._rule_repo = RuleRepo()
        self._event_processor = EventProcessor()

        self._person_repo = PersonRepo()
        self._person_service = PersonService(self._person_repo, self._api_client)
        self._home_profile_service = HomeProfileService(self._person_service)
        self._task_service = TaskService()

        self._device_status_cache: dict[str, str] = {}

        set_collector(self._collector)
        set_event_classifier(self._event_classifier)
        set_rule_engine(self._rule_engine)
        set_sensor_log_repo(self._sensor_log_repo)
        set_event_repo(self._event_repo)
        set_rule_repo(self._rule_repo)
        set_event_processor(self._event_processor)

        self._register_mqtt_callbacks()

        if not self._offline_mode:
            self._try_connect_mqtt()

        self._initialized = True
        logger.info("Manager initialization completed (offline_mode=%s)", self._offline_mode)

    def _try_connect_mqtt(self):
        try:
            from heiman.mqtt_service import get_mqtt_service
            from heiman.shared_state import get_current_token

            mqtt_service = get_mqtt_service()
            if not mqtt_service.is_connected:
                token_info = get_current_token()
                if token_info:
                    access_token = token_info.get("access_token")
                    user_id = token_info.get("user_id")
                    if access_token and user_id:
                        import asyncio
                        asyncio.create_task(mqtt_service.connect(access_token, user_id))
                        logger.info("[Manager] MQTT connection initiated with restored token")
                    else:
                        logger.warning("[Manager] Cannot connect MQTT: missing access_token or user_id")
                else:
                    logger.warning("[Manager] Cannot connect MQTT: no token available")
            else:
                logger.info("[Manager] MQTT already connected")
        except Exception as e:
            logger.error("[Manager] Failed to initiate MQTT connection: %s", e)

    def _register_mqtt_callbacks(self):
        try:
            from heiman.mqtt_service import get_mqtt_service

            mqtt_service = get_mqtt_service()
            mqtt_service.register_device_callback(self._on_mqtt_device_update)
            mqtt_service.register_event_callback(self._on_mqtt_event)
            logger.info("[Manager] Registered MQTT callbacks")
        except Exception as e:
            logger.warning("[Manager] Failed to register MQTT callbacks: %s", e)

    def _on_mqtt_device_update(self, device_id: str, data: dict, topic: str = ""):
        try:
            logger.info("[Manager] MQTT device update: %s", device_id)
            properties = data.get("properties", data)
            if not properties:
                return

            self._adapter.update_from_mqtt(device_id, properties, topic)
            logger.debug("[Manager] Updated sensor data for %s", device_id)

            try:
                from heiman.service.event_bus import get_event_bus

                bus = get_event_bus()
                async def publish_update():
                    await bus.publish({
                        "event": "device_update",
                        "id": str(uuid4()),
                        "data": {
                            "device_id": device_id,
                            "properties": properties,
                            "timestamp": datetime.now().isoformat(),
                        },
                    })
                    logger.debug("[Manager] Device update published to event bus: %s", device_id)

                if hasattr(self, "_event_loop"):
                    self._event_loop.call_soon_threadsafe(
                        asyncio.create_task, publish_update()
                    )
                else:
                    logger.warning("[Manager] Event loop not available for device update")
            except Exception as e:
                logger.warning("[Manager] Failed to publish device update to event bus: %s", e)
        except Exception as e:
            logger.error("[Manager] Error handling MQTT device update: %s", e)

    def _on_mqtt_event(self, device_id: str, event_type: str, payload: dict, topic: str = ""):
        try:
            logger.info("[Manager] MQTT event: %s - %s", device_id, event_type)

            try:
                from heiman.service.event_processor import get_event_processor
                event_processor = get_event_processor()

                async def process_mqtt_event():
                    if topic:
                        await event_processor.process_event(topic, payload)

                if hasattr(self, "_event_loop"):
                    self._event_loop.call_soon_threadsafe(
                        asyncio.create_task, process_mqtt_event()
                    )
                else:
                    logger.warning("[Manager] Event loop not available for MQTT event")
            except Exception as e:
                logger.warning("[Manager] Failed to process MQTT event: %s", e)
        except Exception as e:
            logger.error("[Manager] Error handling MQTT event: %s", e)

    def detect_device_status_changes(self, devices: list[dict]) -> list[SensorEvent]:
        """Detect device online/offline status changes when fetching the device list.

        Compares current device statuses against the previously known cache and
        creates events only for actual online↔offline transitions.
        """
        events: list[SensorEvent] = []
        current_statuses: dict[str, str] = {}

        for device in devices:
            device_id = str(device.get("id", ""))
            if not device_id:
                continue

            status = str(device.get("status", "offline")).lower()
            current_statuses[device_id] = status

            previous = self._device_status_cache.get(device_id)
            if previous is None:
                continue

            if previous == status:
                continue

            device_name = device.get("name", device_id)
            room_name = device.get("room", "") or None
            home_id = device.get("home_id", "") or None

            if status == "offline":
                events.append(SensorEvent(
                    event_id=str(uuid4()),
                    event_type=SensorEventType.DEVICE_OFFLINE,
                    level=SensorEventLevel.WARNING,
                    did=device_id,
                    device_name=device_name,
                    room_name=room_name,
                    home_id=home_id,
                    description=f"设备 {device_name} 离线",
                    raw_data={"previous_status": previous, "current_status": status, "source": "device_list"},
                    timestamp=datetime.now(),
                    acknowledged=False,
                ))
                logger.info("[Manager] Device status change: %s %s->offline", device_id, previous)
                self._record_obs_event("device_offline", "device_list", {"device_id": device_id, "device_name": device_name, "previous": previous})
            elif previous == "offline" and status in ("online", "normal"):
                events.append(SensorEvent(
                    event_id=str(uuid4()),
                    event_type=SensorEventType.DEVICE_ONLINE,
                    level=SensorEventLevel.INFO,
                    did=device_id,
                    device_name=device_name,
                    room_name=room_name,
                    home_id=home_id,
                    description=f"设备 {device_name} 上线",
                    raw_data={"previous_status": previous, "current_status": status, "source": "device_list"},
                    timestamp=datetime.now(),
                    acknowledged=False,
                ))
                logger.info("[Manager] Device status change: %s %s->online", device_id, previous)
                self._record_obs_event("device_online", "device_list", {"device_id": device_id, "device_name": device_name, "previous": previous})

        self._device_status_cache = current_statuses
        return events

    def _record_obs_event(self, event_type: str, source: str, payload: dict):
        """Record an observability event to the metrics DB."""
        try:
            from heiman.observability.recorder import get_recorder
            recorder = get_recorder()
            if recorder:
                recorder.record_event(event_type, source, payload)
        except Exception as e:
            logger.debug("[Manager] Failed to record observability event: %s", e)

    async def _initialize_api_client(self) -> HeimanApiClient:
        client = HeimanApiClient()

        # 优先尝试使用保存的 OAuth token 恢复会话
        try:
            from heiman.shared_state import load_token_from_db
            logger.info("[Manager] Attempting to load OAuth token from database...")
            token = load_token_from_db()
            logger.info("[Manager] Load token result: %s", "NOT None" if token else "None")
            if token:
                user_id = token.get("user_id", "")
                access_token = token.get("access_token", "")
                refresh_token = token.get("refresh_token", "")
                expires_at = token.get("expires_at", 0)
                now = time.time()

                if user_id and access_token and expires_at > now:
                    logger.info("[Manager] Attempting to restore session from saved OAuth token")
                    success = await client.login_with_oauth_token(access_token, user_id)
                    if success:
                        logger.info("[Manager] Session restored successfully via OAuth token")
                        return client
                    else:
                        logger.warning("[Manager] Failed to restore session with OAuth token")
                elif user_id and refresh_token and expires_at <= now:
                    logger.info("[Manager] Token expired, attempting to refresh with refresh_token")
                    try:
                        from heiman_mcp.client.heiman import HeimanClient
                        from heiman.config import get_settings
                        from heiman.shared_state import set_current_token
                        from datetime import datetime

                        settings = get_settings()
                        oauth_client = HeimanClient(base_url=settings.heiman.api_url, token=None)
                        token_data = await oauth_client.refresh_access_token(
                            refresh_token=refresh_token,
                            client_id=settings.heiman.client_id,
                            client_secret=settings.heiman.client_secret,
                        )
                        await oauth_client.close()

                        new_access_token = token_data.get("access_token")
                        new_refresh_token = token_data.get("refresh_token")

                        if not new_access_token:
                            logger.warning(
                                "[Manager] No access token in refresh response: %s",
                                str(token_data)[:500],
                            )

                        if new_access_token:
                            logger.info("[Manager] Token refreshed successfully")
                            new_expires_at = datetime.now().timestamp() + (token_data.get("expires_in", 3600))
                            token_info = {
                                "access_token": new_access_token,
                                "refresh_token": new_refresh_token or refresh_token,
                                "expires_at": new_expires_at,
                                "user_id": user_id,
                            }
                            set_current_token(token_info)

                            success = await client.login_with_oauth_token(new_access_token, user_id)
                            if success:
                                logger.info("[Manager] Session restored successfully after token refresh")
                                return client
                            else:
                                logger.warning("[Manager] Failed to restore session after token refresh")
                    except Exception as e:
                        logger.warning("[Manager] Token refresh failed: %s", e)
        except Exception as e:
            logger.warning("[Manager] Could not load saved OAuth token: %s", e)

        # 如果没有保存的 token 或恢复失败，尝试使用 email/password 登录
        for attempt in range(LOGIN_MAX_RETRIES):
            try:
                logger.info("API login attempt %d/%d", attempt + 1, LOGIN_MAX_RETRIES)
                success = await asyncio.wait_for(
                    client.login(),
                    timeout=LOGIN_TIMEOUT_SECONDS,
                )
                if success:
                    return client
                logger.warning("Login returned failure on attempt %d", attempt + 1)
            except asyncio.TimeoutError:
                logger.warning(
                    "Login attempt %d timed out after %.1fs",
                    attempt + 1,
                    LOGIN_TIMEOUT_SECONDS,
                )
            except Exception as e:
                logger.warning("Login attempt %d failed: %s", attempt + 1, e)

            if attempt < LOGIN_MAX_RETRIES - 1:
                logger.info("Retrying in %d seconds...", LOGIN_RETRY_DELAY)
                await asyncio.sleep(LOGIN_RETRY_DELAY)

        logger.error(
            "All %d login attempts failed, client will operate in unauthenticated mode",
            LOGIN_MAX_RETRIES,
        )
        return client

    @property
    def api_client(self) -> HeimanApiClient:
        return self._api_client

    @property
    def adapter(self) -> SensorDeviceAdapter:
        return self._adapter

    @property
    def collector(self) -> SensorCollector:
        return self._collector

    @property
    def event_classifier(self) -> EventClassifier:
        return self._event_classifier

    @property
    def rule_engine(self) -> RuleEngine:
        return self._rule_engine

    @property
    def sensor_log_repo(self) -> SensorLogRepo:
        return self._sensor_log_repo

    @property
    def event_repo(self) -> EventRepo:
        return self._event_repo

    @property
    def rule_repo(self) -> RuleRepo:
        return self._rule_repo

    @property
    def event_processor(self) -> EventProcessor:
        return self._event_processor

    @property
    def person_service(self) -> PersonService:
        return self._person_service

    @property
    def home_profile_service(self) -> HomeProfileService:
        return self._home_profile_service

    @property
    def task_service(self) -> TaskService:
        return self._task_service


_manager_instance: Manager | None = None


def get_manager():
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = Manager()
    return _manager_instance