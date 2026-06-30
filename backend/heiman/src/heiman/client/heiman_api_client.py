import logging
import asyncio
import time
from datetime import datetime
from typing import Optional, List, Dict

from heiman.config import get_settings
from heiman.schema.sensor import SensorType, SensorData, SensorStatus

from heiman_mcp.client.heiman import HeimanClient
from heiman_mcp.exceptions.errors import HeimanAPIError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3

PROPERTY_MAP = {
    "SmokeSensorState": SensorType.SMOKE,
    "CurrentTemperature": SensorType.TEMPERATURE,
    "CurrentHumidity": SensorType.HUMIDITY,
    "GasSensorState": SensorType.CO,
    "WaterSensorState": SensorType.WATER,
    "ContactState": SensorType.CONTACT,
    "SwitchState": SensorType.CONTACT,
    "OF": SensorType.MOTION,
    "DetectState": SensorType.MOTION,
    "MotionState": SensorType.MOTION,
    "Status": SensorType.PLUG,
    "OnOff": SensorType.PLUG,
    "LightSwitch": SensorType.PLUG,
    "AlarmState": SensorType.SIREN,
    "SirenState": SensorType.SIREN,
    "ButtonState": SensorType.BUTTON,
    "Press": SensorType.BUTTON,
    "coValue": SensorType.CO,
    "temperature": SensorType.TEMPERATURE,
    "humidity": SensorType.HUMIDITY,
    "smoke": SensorType.SMOKE,
    "gas": SensorType.CO,
    "water": SensorType.WATER,
    "contact": SensorType.CONTACT,
    "switch": SensorType.CONTACT,
    "motion": SensorType.MOTION,
    "pir": SensorType.MOTION,
    "plug": SensorType.PLUG,
    "siren": SensorType.SIREN,
    "button": SensorType.BUTTON,
}

UNIT_MAP = {
    SensorType.TEMPERATURE: "℃",
    SensorType.HUMIDITY: "%",
    SensorType.CO: "ppm",
}

PRODUCT_NAME_MAP = [
    ("烟雾", SensorType.SMOKE),
    ("烟感", SensorType.SMOKE),
    ("smoke", SensorType.SMOKE),
    ("燃气", SensorType.CO),
    ("gas", SensorType.CO),
    ("CO_", SensorType.CO),
    ("_CO", SensorType.CO),
    ("水浸", SensorType.WATER),
    ("水位", SensorType.WATER),
    ("water", SensorType.WATER),
    ("温湿度", SensorType.TEMPERATURE),
    ("温度", SensorType.TEMPERATURE),
    ("temp", SensorType.TEMPERATURE),
    ("humidity", SensorType.HUMIDITY),
    ("门磁", SensorType.CONTACT),
    ("门窗", SensorType.CONTACT),
    ("contact", SensorType.CONTACT),
    ("人体", SensorType.MOTION),
    ("存在", SensorType.MOTION),
    ("pir", SensorType.MOTION),
    ("PIR", SensorType.MOTION),
    ("motion", SensorType.MOTION),
    ("插座", SensorType.PLUG),
    ("开关", SensorType.PLUG),
    ("switch", SensorType.PLUG),
    ("plug", SensorType.PLUG),
    ("声光", SensorType.SIREN),
    ("警号", SensorType.SIREN),
    ("siren", SensorType.SIREN),
    ("应急", SensorType.BUTTON),
    ("紧急", SensorType.BUTTON),
    ("按钮", SensorType.BUTTON),
    ("button", SensorType.BUTTON),
    ("SOS", SensorType.BUTTON),
    ("sos", SensorType.BUTTON),
    ("网关", SensorType.GATEWAY),
    ("gateway", SensorType.GATEWAY),
    ("GW", SensorType.GATEWAY),
    ("gw", SensorType.GATEWAY),
    ("遥控", SensorType.REMOTE),
    ("remote", SensorType.REMOTE),
]

DEVICE_TYPE_MAP = {
    "smoke": SensorType.SMOKE,
    "co": SensorType.CO,
    "water": SensorType.WATER,
    "temperature": SensorType.TEMPERATURE,
    "humidity": SensorType.HUMIDITY,
    "door": SensorType.CONTACT,
    "window": SensorType.CONTACT,
    "contact": SensorType.CONTACT,
    "开关": SensorType.CONTACT,
    "motion": SensorType.MOTION,
    "pir": SensorType.MOTION,
    "plug": SensorType.PLUG,
    "siren": SensorType.SIREN,
    "button": SensorType.BUTTON,
    "gateway": SensorType.GATEWAY,
    "remote": SensorType.REMOTE,
}

ICON_MAP = {
    SensorType.SMOKE: "smoke",
    SensorType.TEMPERATURE: "temperature",
    SensorType.HUMIDITY: "humidity",
    SensorType.CO: "gas",
    SensorType.WATER: "water",
}


class HeimanApiClient:
    def __init__(self):
        import asyncio
        settings = get_settings()
        self._api_url = settings.heiman.api_url
        self._app_id = settings.heiman.app_id
        self._email = settings.heiman.email
        self._password = settings.heiman.password
        self._heiman_client: HeimanClient | None = None
        self._access_token: str | None = None
        self._user_id: str | None = None
        self._initialized = False
        self._homes_cache: list = []
        self._devices_cache: dict = {}
        self._cache_expiry: datetime | None = None
        self._init_lock = asyncio.Event()
        self._init_lock.set()  # 默认不阻塞

    def _create_client(self, access_token: str) -> HeimanClient:
        logger.info(
            "[HEIMAN API CLIENT] Creating HeimanClient - api_url=%s, token_length=%d",
            self._api_url,
            len(access_token) if access_token else 0,
        )
        settings = get_settings()
        # 注意：海曼 API 使用自签名证书，需要禁用 SSL 验证
        return HeimanClient(
            base_url=self._api_url,
            token=access_token,
            timeout=DEFAULT_TIMEOUT,
            retries=DEFAULT_RETRIES,
            verify_ssl=False,
            tenant_id=settings.heiman.tenant_id,
            accept_language=settings.heiman.language,
        )

    async def login_with_oauth_token(self, access_token: str, user_id: str) -> bool:
        try:
            logger.info(
                "[HEIMAN API] OAuth2 login - access_token_length=%d, user_id=%s",
                len(access_token) if access_token else 0,
                user_id,
            )

            await self._set_initializing()

            self._access_token = access_token
            self._user_id = user_id

            self._heiman_client = self._create_client(access_token)

            try:
                user_info = await self._heiman_client.get_current_user()
                logger.info(
                    "[HEIMAN API] OAuth2 token validation successful, user_info type: %s, content: %s",
                    type(user_info).__name__,
                    str(user_info)[:500] if user_info else "None",
                )
                if user_info and isinstance(user_info, dict):
                    result = user_info.get("result")
                    if result and isinstance(result, dict):
                        self._user_id = str(result.get("id", user_id))
                        logger.info("[HEIMAN API] Updated user_id from API: %s", self._user_id)
                    elif isinstance(user_info.get("id")):
                        self._user_id = str(user_info.get("id"))
                        logger.info("[HEIMAN API] Updated user_id from direct API response: %s", self._user_id)
                    else:
                        logger.warning("[HEIMAN API] User info response has no 'result' or 'id', using provided user_id: %s", user_id)
                else:
                    logger.warning("[HEIMAN API] User info is not a valid dict, using provided user_id: %s", user_id)
            except Exception as e:
                logger.warning(
                    "[HEIMAN API] OAuth2 token validation failed: %s, using provided user_id: %s",
                    e,
                    user_id,
                )

            self._initialized = True
            try:
                await self._refresh_cache()
            except Exception as cache_error:
                logger.warning(
                    "[HEIMAN API] Cache refresh failed: %s, continuing without cached data",
                    cache_error,
                )
            
            await self._set_initialized()
            logger.info("[HEIMAN API] OAuth2 login completed successfully")
            return True

        except Exception as e:
            logger.error("[HEIMAN API] OAuth2 login failed: %s", e)
            self._cleanup()
            await self._set_initialized()
            return False

    def _cleanup(self):
        if self._heiman_client:
            import asyncio

            try:
                asyncio.create_task(self._heiman_client.close())
            except Exception:
                pass
        self._heiman_client = None
        self._access_token = None
        self._user_id = None
        self._initialized = False
        self._homes_cache = []
        self._devices_cache = {}
        logger.info("[HEIMAN API] Client cleaned up")

    async def login(self) -> bool:
        try:
            if not self._email:
                logger.warning(
                    "[HEIMAN API] Email not configured, skipping login. Use OAuth2 login instead."
                )
                return False

            self._heiman_client = self._create_client("")

            result = await self._heiman_client.get_user_list(
                page_size=1, page_number=1, app_id=self._app_id, email=self._email
            )

            logger.info(
                "[HEIMAN API] Login request result: data=%s",
                result,
            )

            if result.get("status") == 200 and result.get("result", {}).get("list"):
                user = result["result"]["list"][0]
                self._user_id = user.get("id")
                self._access_token = user.get("token", "")

                if self._access_token:
                    self._heiman_client = self._create_client(self._access_token)

                logger.info("[HEIMAN API] Logged in successfully, user_id: %s", self._user_id)
                self._initialized = True
                await self._refresh_cache()
                return True
            return False
        except Exception as e:
            logger.error("[HEIMAN API] Login failed: %s", e)
            self._cleanup()
            return False

    @property
    def is_authenticated(self) -> bool:
        if not self._init_lock.is_set():
            logger.debug("[HEIMAN API] Waiting for initialization to complete...")
        return (
            self._user_id is not None
            and self._heiman_client is not None
            and self._initialized
        )

    async def _try_refresh_token(self) -> bool:
        """用 refresh_token 刷新 access_token,更新 client 和存储。"""
        try:
            from heiman.shared_state import get_current_token, set_current_token

            token_info = get_current_token()
            if not token_info or not token_info.get("refresh_token"):
                logger.warning("[HEIMAN API] No refresh_token available, cannot refresh")
                return False

            refresh_token = token_info["refresh_token"]
            user_id = token_info.get("user_id", "")
            settings = get_settings()

            logger.info("[HEIMAN API] Refreshing access_token via refresh_token")

            oauth_client = HeimanClient(
                base_url=settings.heiman.api_url, token=None, verify_ssl=False
            )
            try:
                token_data = await oauth_client.refresh_access_token(
                    refresh_token=refresh_token,
                    client_id=settings.heiman.client_id,
                    client_secret=settings.heiman.client_secret,
                )
            finally:
                await oauth_client.close()

            new_access_token = token_data.get("access_token")
            if not new_access_token:
                logger.warning(
                    "[HEIMAN API] Token refresh failed: no access_token in response: %s",
                    str(token_data)[:500],
                )
                return False

            new_refresh_token = token_data.get("refresh_token") or refresh_token
            new_expires_at = time.time() + (token_data.get("expires_in", 3600))

            # 更新存储(内存 + DB)
            set_current_token({
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "expires_at": new_expires_at,
                "user_id": user_id,
            })

            # 更新当前 client 的 token
            self._access_token = new_access_token
            self._heiman_client = self._create_client(new_access_token)

            logger.info("[HEIMAN API] Token refreshed successfully, new expires_at=%s", datetime.fromtimestamp(new_expires_at).isoformat())
            return True

        except Exception as e:
            logger.error("[HEIMAN API] Token refresh failed: %s", e)
            return False

    async def _ensure_valid_token(self) -> bool:
        """检查 token 是否即将过期(5分钟内),若是则主动刷新。"""
        try:
            from heiman.shared_state import get_current_token

            token_info = get_current_token()
            if not token_info:
                return True  # 没有 stored token,跳过(可能是 email/password 登录)

            expires_at = token_info.get("expires_at", 0)
            now = time.time()
            if expires_at - now > 300:
                return True  # 还没到期

            logger.info("[HEIMAN API] Token expiring soon (expires_at=%s, now=%s), refreshing proactively",
                        datetime.fromtimestamp(expires_at).isoformat(),
                        datetime.fromtimestamp(now).isoformat())
            return await self._try_refresh_token()
        except Exception:
            return True  # 出错不阻塞,让后续请求自行处理 401

    async def _wait_for_init(self):
        """等待初始化完成（如果有正在进行）"""
        try:
            await asyncio.wait_for(self._init_lock.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("[HEIMAN API] Timeout waiting for initialization")

    async def _set_initializing(self):
        """开始初始化，阻塞后续请求"""
        self._init_lock.clear()
        logger.info("[HEIMAN API] Starting initialization, blocking new requests")

    async def _set_initialized(self):
        """完成初始化，允许后续请求"""
        self._init_lock.set()
        logger.info("[HEIMAN API] Initialization complete, allowing new requests")

    async def _refresh_cache(self):
        try:
            logger.info("[HEIMAN API] Refreshing cache")
            self._homes_cache = await self._fetch_home_list()
            self._cache_expiry = datetime.now()
            logger.info(
                "[HEIMAN API] Cache refreshed: %d homes",
                len(self._homes_cache),
            )
        except Exception as e:
            logger.error("[HEIMAN API] Cache refresh failed: %s", e)

    async def _fetch_home_list(self) -> list:
        if not self._heiman_client:
            return []

        if not self._user_id:
            logger.warning("[HEIMAN API] user_id is required for get_home_list")
            return []

        for attempt in range(2):  # 最多重试 1 次(401 后刷新 token)
            try:
                result = await self._heiman_client.get_home_list(user_id=self._user_id)

                logger.info(
                    "[HEIMAN API] get_home_list: data=%s",
                    result,
                )

                if result.get("status") == 200:
                    homes = result.get("result", [])
                    if not isinstance(homes, list):
                        homes = []
                    return homes
                return []
            except HeimanAPIError as e:
                if e.status == 401 and attempt == 0:
                    logger.warning("[HEIMAN API] get_home_list got 401, refreshing token and retrying")
                    refreshed = await self._try_refresh_token()
                    if refreshed:
                        continue
                    logger.error("[HEIMAN API] Token refresh failed, cannot retry get_home_list")
                    return []
                logger.error("[HEIMAN API] Get home list failed: %s", e)
                return []
            except Exception as e:
                logger.error("[HEIMAN API] Get home list failed: %s", e)
                return []
        return []

    async def get_home_list(self) -> list:
        await self._wait_for_init()
        if not self.is_authenticated:
            await self.login()
            if not self.is_authenticated:
                return []

        await self._ensure_valid_token()

        if (
            not self._homes_cache
            or self._cache_expiry
            and (datetime.now() - self._cache_expiry).total_seconds() > 300
        ):
            await self._refresh_cache()

        return self._homes_cache

    async def _fetch_devices(self, home_id: str) -> list:
        if not self._heiman_client:
            return []

        try:
            property_identifiers = [
                "ArmModeControl", "GatewayHandleStatus", "GasSensorState", "Alarm",
                "RingSwitch", "LockState", "AlarmSwitch", "LightSwitch", "BWY", "SWY",
                "PowerSwitch_1", "PowerSwitch_2", "PowerSwitch_3", "CurtainPosition",
                "PowerSwitch", "RealTimePower", "SmokeSensorState", "CurrentTemperature",
                "CurrentHumidity", "TamperState", "SwitchState", "alarmEnable",
                "WaterSensorState", "FreezingPointAlarm", "PM25", "PM10", "co2",
                "OF", "ON", "GatewayMac", "Icon", "UserName", "HeatSensorStatus",
                "BatteryPercentage", "UnderVoltError", "MasterDevice", "LocalSceneControl",
                "outdoorTemperature", "SensorLifeStatus", "TempAlarmType", "HumiAlarmType",
                "TempShowType", "HumidityShowType", "MainPowerStatus", "MotionAlarmState",
                "ContactState", "BrightnessLevel", "Volume", "RGBColor", "RingOption",
                "PlayRing", "peopleState", "activeState", "alarmType", "peopleStateSwitch",
                "activeStateSwitch", "battery_value", "faultSta", "alarmSta",
                "CertificationType", "coValue", "CONC", "GAS"
            ]

            result = await self._heiman_client.get_device_list(
                home_id=home_id,
                user_id=self._user_id,
                page_size=200,
                page_number=1,
                property_identifiers=property_identifiers,
            )

            logger.info(
                "[HEIMAN API] get_device_list for home %s: status=%s, result=%s",
                home_id,
                result.get("status"),
                result,
            )

            if result.get("status") == 200:
                result_data = result.get("result", {})
                if isinstance(result_data, list):
                    devices = result_data
                elif isinstance(result_data, dict):
                    devices = result_data.get("data", []) 
                else:
                    devices = []
                if not isinstance(devices, list):
                    devices = []
                logger.info("[HEIMAN API] Parsed devices count: %d", len(devices))
                return devices
            return []
        except Exception as e:
            logger.error("[HEIMAN API] Get devices failed for home %s: %s", home_id, e)
            return []

    async def get_devices(self, home_id: str | None = None) -> dict[str, dict]:
        await self._wait_for_init()
        if not self.is_authenticated:
            await self.login()
            if not self.is_authenticated:
                return {}

        if not home_id:
            homes = await self.get_home_list()
            if not homes:
                return {}
            home_id = homes[0].get("id", homes[0].get("homeId"))

        if not home_id:
            return {}

        if (
            home_id not in self._devices_cache
            or self._cache_expiry
            and (datetime.now() - self._cache_expiry).total_seconds() > 300
        ):
            self._devices_cache[home_id] = await self._fetch_devices(home_id)

        devices_dict = {}
        for device in self._devices_cache.get(home_id, []):
            device_id = str(device.get("deviceId", device.get("id", "")))
            if device_id:
                devices_dict[device_id] = device

        return devices_dict

    async def get_all_devices(self, home_id: str | None = None) -> list[dict]:
        devices_dict = await self.get_devices(home_id)
        return list(devices_dict.values())

    async def get_device_info(self, device_id: str) -> dict:
        if not self._heiman_client:
            return {}

        try:
            result = await self._heiman_client.get_device_info(device_id=device_id)

            logger.info(
                "[HEIMAN API] get_device_info for %s: data=%s",
                device_id,
                result,
            )

            if result.get("status") == 200:
                return result.get("result", {})
            return {}
        except Exception as e:
            logger.error("[HEIMAN API] Get device info failed for %s: %s", device_id, e)
            return {}

    async def get_device_properties(self, device_id: str) -> dict:
        if not self._heiman_client:
            return {}

        try:
            result = await self._heiman_client.get_device_detail(device_id=device_id)

            logger.info(
                "[HEIMAN API] get_device_properties for %s: data=%s",
                device_id,
                result,
            )

            if result.get("status") == 200:
                return result.get("result", {}).get("properties", {})
            return {}
        except Exception as e:
            logger.error(
                "[HEIMAN API] Get device properties failed for %s: %s", device_id, e
            )
            return {}

    async def get_user_info(self) -> dict:
        await self._wait_for_init()
        if not self._heiman_client:
            return {}

        try:
            result = await self._heiman_client.get_current_user()

            logger.info(
                "[HEIMAN API] get_user_info: data=%s",
                result,
            )

            if result.get("status") == 200:
                return result.get("result", {})
            return {}
        except Exception as e:
            logger.error("[HEIMAN API] Get user info failed: %s", e)
            return {}

    async def get_alarm_logs(self, home_id: str | None = None, limit: int = 100) -> list[dict]:
        if not self._heiman_client:
            return []

        try:
            result = await self._heiman_client.query_push_messages(
                page_size=limit, page_number=1, home_id=home_id
            )

            logger.info(
                "[HEIMAN API] get_alarm_logs: data=%s",
                str(result)[:500],
            )

            if result.get("status") == 200:
                logs = result.get("result", {}).get("list", [])
                if not isinstance(logs, list):
                    logs = []
                
                devices = await self.get_devices(home_id)
                adapted_logs = []
                for log in logs:
                    adapted = self._adapt_event_data(log, devices, home_id)
                    if adapted:
                        adapted_logs.append(adapted)
                
                return adapted_logs
            return []
        except Exception as e:
            logger.error("[HEIMAN API] Get alarm logs failed: %s", e)
            return []

    def _adapt_event_data(self, log: dict, devices: dict[str, dict], home_id: str | None = None) -> dict | None:
        try:
            device_id = str(log.get("deviceId", log.get("did", log.get("id", ""))))
            device = devices.get(device_id, {})
            device_name = log.get("deviceName", log.get("name", device.get("deviceName", device.get("name", ""))))
            
            message = log.get("message", log.get("content", log.get("description", log.get("pushContent", ""))))
            if not message:
                alarm_type = log.get("alarmType", log.get("type", ""))
                alarm_name = log.get("alarmName", log.get("name", ""))
                message = alarm_name or alarm_type or "事件"
            
            level = log.get("level", log.get("alarmLevel", ""))
            if not level or level not in ["critical", "high", "medium", "low", "warning", "info"]:
                alarm_type = str(log.get("alarmType", log.get("type", ""))).lower()
                if "alarm" in alarm_type or "报警" in str(message):
                    level = "high"
                elif "warning" in alarm_type or "警告" in str(message):
                    level = "warning"
                elif "info" in alarm_type or "信息" in str(message) or "在线" in str(message) or "离线" in str(message):
                    level = "info"
                else:
                    level = "info"
            
            event_type = log.get("event_type", log.get("eventType", ""))
            if not event_type or event_type not in ["alarm", "warning", "info"]:
                if level in ["critical", "high", "medium"]:
                    event_type = "alarm"
                elif level == "warning":
                    event_type = "warning"
                else:
                    event_type = "info"
            
            sensor_type = None
            device_type = str(log.get("deviceType", device.get("deviceType", ""))).lower()
            product_name = str(log.get("productName", device.get("productName", ""))).lower()
            alarm_type_str = str(log.get("alarmType", log.get("type", ""))).lower()
            
            if "sensor_type" in log:
                sensor_type = str(log.get("sensor_type", "")).lower()
            
            if sensor_type is None or sensor_type == "":
                for keyword, st in PRODUCT_NAME_MAP:
                    if keyword.lower() in product_name or keyword.lower() in alarm_type_str or keyword.lower() in device_type:
                        sensor_type = st.value
                        break
            
            if sensor_type is None or sensor_type == "":
                for prop_key, st in PROPERTY_MAP.items():
                    if prop_key.lower() in alarm_type_str:
                        sensor_type = st.value
                        break
            
            if sensor_type is None or sensor_type == "":
                device_name_lower = str(device_name).lower()
                for type_name, st in DEVICE_TYPE_MAP.items():
                    if type_name in device_name_lower:
                        sensor_type = st.value
                        break
            
            if sensor_type is None or sensor_type == "":
                sensor_type = "undefined"
            
            timestamp = log.get("timestamp", log.get("time", log.get("createTime", log.get("updatedTime", ""))))
            if not timestamp:
                timestamp = datetime.now().isoformat()
            
            event_id = str(log.get("id", log.get("eventId", log.get("pushId", log.get("recordId", "")))))
            if not event_id:
                event_id = f"{device_id}_{timestamp}"
            
            acknowledged = bool(log.get("acknowledged", log.get("isRead", False)))
            
            return {
                "event_id": event_id,
                "did": device_id,
                "device_name": device_name,
                "sensor_type": sensor_type,
                "event_type": event_type,
                "level": level,
                "message": str(message),
                "description": str(message),
                "timestamp": str(timestamp),
                "acknowledged": acknowledged,
                "home_id": log.get("homeId", home_id if home_id else ""),
                "raw_data": log,
            }
        except Exception as e:
            logger.warning("[HEIMAN API] Failed to adapt event data: %s, error: %s", str(log)[:200], e)
            return None

    async def control_device(
        self, device_id: str, property_identifier: str, value: bool | int | float
    ) -> bool:
        if not self._heiman_client:
            return False

        try:
            result = await self._heiman_client.get_device_info(device_id=device_id)

            logger.info(
                "[HEIMAN API] control_device %s: property=%s, value=%s, result=%s",
                device_id,
                property_identifier,
                value,
                result,
            )

            return result.get("status") == 200
        except Exception as e:
            logger.error("[HEIMAN API] Control device %s failed: %s", device_id, e)
            return False

    def _parse_sensor_data(self, device: dict) -> SensorData | None:
        sensor_type = None
        value = 0
        unit = ""
        device_id = str(device.get("deviceId", device.get("id", "")))
        device_name = device.get("deviceName", device.get("name", ""))
        room_id = str(device.get("roomId", ""))
        home_id = str(device.get("homeId", ""))
        room_name = device.get("roomName", "")
        product_id = str(device.get("productId", ""))

        if product_id:
            product_info = self._get_product_info(product_id)
            if product_info:
                classified_name = product_info.get("classified_name", "")
                product_name = product_info.get("name", "")
                for keyword, sensor_type_enum in PRODUCT_NAME_MAP:
                    if keyword.lower() in classified_name.lower() or keyword.lower() in product_name.lower():
                        sensor_type = sensor_type_enum
                        unit = UNIT_MAP.get(sensor_type, "")
                        break

        properties = device.get("properties", {})
        if sensor_type is None and isinstance(properties, dict):
            for prop_id, prop_value in properties.items():
                if prop_id in PROPERTY_MAP:
                    sensor_type = PROPERTY_MAP[prop_id]
                    value = prop_value if prop_value is not None else 0
                    unit = UNIT_MAP.get(sensor_type, "")
                    break

        if sensor_type is None:
            derive_metadata = device.get("deriveMetadata", "[]")
            if isinstance(derive_metadata, str):
                try:
                    import json
                    derive_metadata = json.loads(derive_metadata)
                except (json.JSONDecodeError, TypeError):
                    derive_metadata = []

            if isinstance(derive_metadata, list):
                for prop in derive_metadata:
                    if isinstance(prop, dict):
                        prop_id = prop.get("property", "")
                        prop_val = prop.get("value")
                        if prop_id in PROPERTY_MAP:
                            sensor_type = PROPERTY_MAP[prop_id]
                            if prop_val is not None:
                                try:
                                    num_val = prop.get("numberValue")
                                    if num_val is not None:
                                        value = num_val
                                    else:
                                        value = float(prop_val) if prop_val else 0
                                except (ValueError, TypeError):
                                    value = 0
                            unit = UNIT_MAP.get(sensor_type, "")
                            break

        if sensor_type is None:
            for prop_key, sensor_type_enum in PROPERTY_MAP.items():
                if prop_key in device:
                    prop_val = device.get(prop_key)
                    if prop_val is not None:
                        sensor_type = sensor_type_enum
                        value = prop_val
                        unit = UNIT_MAP.get(sensor_type, "")
                        break

        if sensor_type is None:
            device_name_lower = str(device_name).lower()
            for type_name, sensor_type_enum in DEVICE_TYPE_MAP.items():
                if type_name in device_name_lower:
                    sensor_type = sensor_type_enum
                    unit = UNIT_MAP.get(sensor_type, "")
                    break

        if sensor_type is None:
            product_name = str(device.get("productName", ""))
            for keyword, sensor_type_enum in PRODUCT_NAME_MAP:
                if keyword.lower() in product_name.lower():
                    sensor_type = sensor_type_enum
                    unit = UNIT_MAP.get(sensor_type, "")
                    break

        if sensor_type is None:
            device_type = device.get("deviceType", {})
            if isinstance(device_type, dict):
                device_type_text = str(device_type.get("text", "")).lower()
                device_type_value = str(device_type.get("value", "")).lower()
                for type_name, sensor_type_enum in DEVICE_TYPE_MAP.items():
                    if type_name in device_type_text or type_name in device_type_value:
                        sensor_type = sensor_type_enum
                        unit = UNIT_MAP.get(sensor_type, "")
                        break

        if sensor_type is None:
            return None

        state_info = device.get("state", {})
        if isinstance(state_info, dict):
            is_online = state_info.get("value", "offline") == "online"
            state_update_time = state_info.get("updateTime") or state_info.get("time")
        else:
            is_online = device.get("online", True)
            if isinstance(is_online, str):
                is_online = is_online.lower() == "online"
            state_update_time = None

        update_time = device.get("updateTime") or device.get("updatedTime") or device.get("createTime") or state_update_time
        if update_time:
            try:
                if isinstance(update_time, (int, float)):
                    if update_time > 1e12:
                        sensor_timestamp = datetime.fromtimestamp(update_time / 1000)
                    else:
                        sensor_timestamp = datetime.fromtimestamp(update_time)
                elif isinstance(update_time, str):
                    from datetime import datetime as dt
                    try:
                        sensor_timestamp = dt.fromisoformat(update_time.replace('Z', '+00:00'))
                    except ValueError:
                        try:
                            sensor_timestamp = dt.strptime(update_time, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            sensor_timestamp = datetime.now()
                else:
                    sensor_timestamp = datetime.now()
            except Exception:
                sensor_timestamp = datetime.now()
        else:
            sensor_timestamp = datetime.now()

        if value is None:
            value = 0
        try:
            value = float(value)
            if value.is_integer():
                value = int(value)
        except (ValueError, TypeError):
            value = 0

        status = self._determine_status(sensor_type, value, bool(is_online))

        return SensorData(
            did=device_id,
            name=device_name,
            sensor_type=sensor_type,
            value=value,
            unit=unit,
            status=status,
            room_id=room_id,
            room_name=room_name,
            home_id=home_id,
            icon=ICON_MAP.get(sensor_type),
            timestamp=sensor_timestamp,
        )

    def _get_product_info(self, product_id: str) -> dict | None:
        try:
            from heiman.database.connector import get_db_connector
            from heiman.database.product_repo import ProductRepo
            db = get_db_connector()
            repo = ProductRepo(db)
            return repo.get_product(product_id)
        except Exception as e:
            logger.debug("[HEIMAN API] Failed to get product info for %s: %s", product_id, e)
            return None

    def _determine_status(
        self, sensor_type: SensorType, value: float | int, is_online: bool
    ) -> SensorStatus:
        if not is_online:
            return SensorStatus.OFFLINE

        if sensor_type == SensorType.SMOKE and value == 1:
            return SensorStatus.ALARM
        elif sensor_type == SensorType.WATER and value == 1:
            return SensorStatus.ALARM
        elif sensor_type == SensorType.CO and int(value) > 0:
            return SensorStatus.ALARM
        elif sensor_type == SensorType.TEMPERATURE:
            if value > 35:
                return SensorStatus.WARNING
            elif value < 5:
                return SensorStatus.WARNING
        elif sensor_type == SensorType.HUMIDITY:
            if value > 80:
                return SensorStatus.WARNING
            elif value < 20:
                return SensorStatus.WARNING

        return SensorStatus.NORMAL

    async def get_sensor_data(self, home_id: str | None = None) -> list[SensorData]:
        await self._wait_for_init()
        if not self.is_authenticated:
            await self.login()
            if not self.is_authenticated:
                return []

        if home_id:
            devices = await self.get_devices(home_id)
        else:
            homes = await self.get_home_list()
            if not homes:
                logger.warning("[HEIMAN API] No homes found")
                return []
            home_id = homes[0].get("id", homes[0].get("homeId"))
            devices = await self.get_devices(home_id)

        rooms = await self.get_room_list(home_id) if home_id else []
        room_name_map: dict[str, str] = {}
        for room in rooms:
            room_id = room.get("roomId", room.get("id", ""))
            room_name = room.get("roomName", room.get("name", ""))
            if room_id and room_name:
                room_name_map[room_id] = room_name

        sensor_data_list = []
        for device in devices.values():
            sensor_data = self._parse_sensor_data(device)
            if sensor_data:
                sensor_data.home_id = home_id or ""
                if sensor_data.room_id and sensor_data.room_id in room_name_map:
                    sensor_data.room_name = room_name_map[sensor_data.room_id]
                sensor_data_list.append(sensor_data)

        logger.info(
            "[HEIMAN API] get_sensor_data: %d sensors found for home %s",
            len(sensor_data_list),
            home_id,
        )

        return sensor_data_list

    async def close(self) -> None:
        if self._heiman_client:
            await self._heiman_client.close()
            logger.info("[HEIMAN API] Client closed")

    async def get_room_list(self, home_id: str) -> list:
        if not self._heiman_client:
            return []

        try:
            for home in self._homes_cache:
                hid = home.get("homeId", home.get("id", ""))
                if str(hid) == str(home_id):
                    room_list = home.get("roomList", [])
                    if room_list and isinstance(room_list, list) and len(room_list) > 0:
                        logger.info(
                            "[HEIMAN API] get_room_list from home cache: home=%s, count=%d",
                            home_id,
                            len(room_list),
                        )
                        return room_list

            result = await self._heiman_client.get_room_list(home_id=home_id)

            logger.info(
                "[HEIMAN API] get_room_list for home %s: status=%s",
                home_id,
                result.get("status"),
            )

            if result.get("status") == 200:
                result_data = result.get("result", {})
                if isinstance(result_data, list):
                    rooms = result_data
                elif isinstance(result_data, dict):
                    rooms = result_data.get("data", []) or result_data.get("list", [])
                else:
                    rooms = []
                if not isinstance(rooms, list):
                    rooms = []
                logger.info("[HEIMAN API] Parsed rooms count: %d", len(rooms))
                return rooms
            return []
        except Exception as e:
            logger.error("[HEIMAN API] Get room list failed for home %s: %s", home_id, e)
            return []

    async def get_home_members(self, home_id: str) -> list:
        if not self._heiman_client:
            return []

        try:
            result = await self._heiman_client.get_home_user_list(home_id=home_id)

            logger.info(
                "[HEIMAN API] get_home_members for home %s: data=%s",
                home_id,
                result,
            )

            if result.get("status") == 200:
                members = result.get("result", {}).get("list", [])
                if not isinstance(members, list):
                    members = []
                return members
            return []
        except Exception as e:
            logger.error(
                "[HEIMAN API] Get home members failed for home %s: %s", home_id, e
            )
            return []