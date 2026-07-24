import logging
import asyncio
import time
import json
from datetime import datetime
from typing import Optional, List, Dict

from heiman.config import get_settings
from heiman.schema.sensor import SensorType, SensorData, SensorStatus

from heiman_mcp.client.heiman import HeimanClient
from heiman_mcp.exceptions.errors import HeimanAPIError, HeimanAuthError

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
    "SwitchState": SensorType.PLUG,
    "OF": SensorType.MOTION,
    "DetectState": SensorType.MOTION,
    "MotionState": SensorType.MOTION,
    "Status": SensorType.PLUG,
    "OnOff": SensorType.PLUG,
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
    "switch": SensorType.PLUG,
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
    "门磁": SensorType.CONTACT,
    "窗磁": SensorType.CONTACT,
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
        # token 刷新频率限制字段
        self._last_refresh_time: float = 0.0         # 上次刷新尝试的时间戳
        self._last_refresh_success: bool = False      # 上次刷新是否成功
        self._consecutive_failures: int = 0           # 连续失败次数
        self._refresh_cooldown: int = 30              # 刷新冷却时间(秒),避免短时间内重复刷新
        self._max_consecutive_failures: int = 5       # 最大连续失败次数,超过后停止自动刷新

    def _create_client(self, access_token: str) -> HeimanClient:
        logger.info(
            "[HEIMAN API CLIENT] Creating HeimanClient - api_url=%s, token_length=%d",
            self._api_url,
            len(access_token) if access_token else 0,
        )
        return HeimanClient(
            base_url=self._api_url,
            token=access_token,
            timeout=DEFAULT_TIMEOUT,
            retries=DEFAULT_RETRIES,
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
        """用 refresh_token 刷新 access_token,更新 client 和存储。

        重要:refresh 失败时不会清除已存储的 token,保留旧 token 以便:
        1. 用户仍可通过旧 access_token(若未过期)继续使用
        2. 避免因临时网络错误或响应格式问题导致 token 被误删
        3. 下次刷新周期可再次尝试

        频率限制:
        - 冷却时间 _refresh_cooldown 秒内不重复刷新(避免短时间内大量刷新请求)
        - 连续失败 _max_consecutive_failures 次后停止自动刷新(需要用户重新登录)
        """
        try:
            from heiman.shared_state import get_current_token, set_current_token

            now = time.time()

            # 1. 冷却时间检查:避免短时间内重复刷新
            elapsed = now - self._last_refresh_time
            if elapsed < self._refresh_cooldown:
                logger.debug(
                    "[HEIMAN API] Token refresh skipped: in cooldown "
                    "(%.1fs elapsed, %.1fs required)",
                    elapsed, self._refresh_cooldown,
                )
                return self._last_refresh_success

            # 2. 连续失败次数检查:超过阈值后停止自动刷新
            if self._consecutive_failures >= self._max_consecutive_failures:
                logger.warning(
                    "[HEIMAN API] Token refresh skipped: %d consecutive failures "
                    "(max=%d), user needs to re-login via OAuth2",
                    self._consecutive_failures, self._max_consecutive_failures,
                )
                return False

            token_info = get_current_token()
            if not token_info:
                logger.warning(
                    "[HEIMAN API] No stored token info, cannot refresh. "
                    "User may need to re-login via OAuth2."
                )
                return False
            if not token_info.get("refresh_token"):
                logger.warning(
                    "[HEIMAN API] No refresh_token in stored token info "
                    "(keys=%s, user_id=%s, expires_at=%s), cannot refresh. "
                    "OAuth2 flow may not have returned refresh_token; user needs to re-login.",
                    list(token_info.keys()),
                    token_info.get("user_id", ""),
                    datetime.fromtimestamp(token_info.get("expires_at", 0)).isoformat() if token_info.get("expires_at") else "unknown",
                )
                return False

            refresh_token = token_info["refresh_token"]
            user_id = token_info.get("user_id", "")
            expires_at = token_info.get("expires_at", 0)

            logger.info(
                "[HEIMAN API] Refreshing access_token via refresh_token - "
                "user_id=%s, token_expired=%s, expires_at=%s, attempt=%d/%d",
                user_id,
                now > expires_at,
                datetime.fromtimestamp(expires_at).isoformat() if expires_at else "never",
                self._consecutive_failures + 1, self._max_consecutive_failures,
            )

            self._last_refresh_time = now

            settings = get_settings()
            oauth_client = HeimanClient(
                base_url=settings.heiman.api_url, token=None
            )
            try:
                token_data = await oauth_client.refresh_access_token(
                    refresh_token=refresh_token,
                    client_id=settings.heiman.client_id,
                    client_secret=settings.heiman.client_secret,
                )
            finally:
                await oauth_client.close()

            logger.info(
                "[HEIMAN API] Refresh token response type=%s, full response=%s",
                type(token_data).__name__, str(token_data)[:800]
            )

            if not isinstance(token_data, dict):
                logger.error(
                    "[HEIMAN API] Token refresh returned unexpected response type: %s, "
                    "keeping existing token",
                    type(token_data).__name__
                )
                self._consecutive_failures += 1
                self._last_refresh_success = False
                return False

            # 兼容两种响应格式:
            # 1. 扁平结构(OAuth2 标准): {"access_token":"xxx","refresh_token":"xxx","expires_in":3600}
            # 2. 嵌套结构(Heiman 业务包装): {"status":200,"result":{"access_token":"xxx",...}}
            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)

            if not new_access_token:
                result = token_data.get("result")
                if isinstance(result, dict):
                    logger.info("[HEIMAN API] Trying nested result field for token data")
                    new_access_token = result.get("access_token")
                    new_refresh_token = result.get("refresh_token") or new_refresh_token
                    expires_in = result.get("expires_in", expires_in)

            if not new_access_token:
                status = token_data.get("status")
                message = token_data.get("message", "")
                logger.error(
                    "[HEIMAN API] Token refresh failed: no access_token in response. "
                    "status=%s, message=%s, result=%s, keys=%s. Keeping existing token.",
                    status, message,
                    str(result)[:200] if result else None,
                    list(token_data.keys()),
                )
                self._consecutive_failures += 1
                self._last_refresh_success = False
                return False

            # 保留旧 refresh_token(若响应未返回新的)
            new_refresh_token = new_refresh_token or refresh_token
            new_expires_at = time.time() + expires_in

            set_current_token({
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "expires_at": new_expires_at,
                "user_id": user_id,
            })

            self._access_token = new_access_token
            self._heiman_client = self._create_client(new_access_token)

            # 刷新成功,重置失败计数
            self._consecutive_failures = 0
            self._last_refresh_success = True

            logger.info(
                "[HEIMAN API] Token refreshed successfully, new expires_at=%s",
                datetime.fromtimestamp(new_expires_at).isoformat()
            )
            return True

        except Exception as e:
            logger.error(
                "[HEIMAN API] Token refresh failed (keeping existing token): %s",
                e, exc_info=True
            )
            self._consecutive_failures += 1
            self._last_refresh_success = False
            return False

    def reset_refresh_state(self):
        """重置刷新状态(用户重新登录后调用)。"""
        self._consecutive_failures = 0
        self._last_refresh_success = False
        self._last_refresh_time = 0.0
        logger.info("[HEIMAN API] Refresh state reset (consecutive_failures=0)")

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

    async def _call_api_with_retry(self, api_call, *args, **kwargs):
        """统一的 API 调用包装器:在 401 时自动刷新 token 并重试一次。

        处理两种 401 场景:
        1. HeimanAuthError - HTTP 层 401(base.py 中 raise_for_status 触发)
        2. HeimanAPIError(status=401) - 业务层 401(响应体中 status=401)
        """
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                return await api_call(*args, **kwargs)
            except HeimanAuthError as e:
                last_exc = e
                if attempt == 0:
                    logger.warning(
                        "[HEIMAN API] %s got 401 (HeimanAuthError), refreshing token and retrying",
                        getattr(api_call, '__name__', str(api_call)),
                    )
                    refreshed = await self._try_refresh_token()
                    if refreshed:
                        continue
                    logger.error("[HEIMAN API] Token refresh failed, cannot retry after 401")
                    raise
                raise
            except HeimanAPIError as e:
                last_exc = e
                if e.status == 401 and attempt == 0:
                    logger.warning(
                        "[HEIMAN API] %s got 401 (HeimanAPIError status=401), refreshing token and retrying",
                        getattr(api_call, '__name__', str(api_call)),
                    )
                    refreshed = await self._try_refresh_token()
                    if refreshed:
                        continue
                    logger.error("[HEIMAN API] Token refresh failed, cannot retry after 401")
                    raise
                raise
        if last_exc:
            raise last_exc

    async def start_token_refresh_loop(self, check_interval: int = 60, refresh_buffer: int = 300):
        """后台定时任务:每 check_interval 秒检查一次 token,在过期前 refresh_buffer 秒主动刷新。

        与业务调用解耦,确保 token 不会因长时间无 API 调用而过期。

        退避策略:
        - 连续失败时,检查间隔会指数增长(check_interval * 2^failures),最长 10 分钟
        - 连续失败 _max_consecutive_failures 次后停止刷新,等待用户重新登录
        - 刷新成功后立即恢复正常检查间隔
        """
        logger.info(
            "[HEIMAN API] Token refresh loop started (check_interval=%ds, refresh_buffer=%ds)",
            check_interval, refresh_buffer,
        )
        while True:
            try:
                # 计算当前实际休眠时间(失败后指数退避)
                if self._consecutive_failures > 0 and self._consecutive_failures < self._max_consecutive_failures:
                    backoff = min(check_interval * (2 ** self._consecutive_failures), 600)
                    logger.info(
                        "[HEIMAN API] Token refresh loop: backing off %ds due to %d consecutive failures",
                        backoff, self._consecutive_failures,
                    )
                    await asyncio.sleep(backoff)
                else:
                    await asyncio.sleep(check_interval)

                # 连续失败次数已达上限,停止自动刷新
                if self._consecutive_failures >= self._max_consecutive_failures:
                    logger.warning(
                        "[HEIMAN API] Token refresh loop: %d consecutive failures reached, "
                        "stopping auto-refresh until user re-login or reset_refresh_state() called",
                        self._consecutive_failures,
                    )
                    continue

                from heiman.shared_state import get_current_token

                token_info = get_current_token()
                if not token_info:
                    # 没有存储的 token(可能是 email/password 登录或未登录),跳过
                    continue

                if not token_info.get("refresh_token"):
                    logger.warning(
                        "[HEIMAN API] Token refresh loop: no refresh_token in stored token "
                        "(token_info keys=%s), cannot auto-refresh; user may need to re-login",
                        list(token_info.keys()),
                    )
                    continue

                expires_at = token_info.get("expires_at", 0)
                now = time.time()
                remaining = expires_at - now

                if remaining > refresh_buffer:
                    # 还没到刷新窗口
                    continue

                if remaining <= 0:
                    logger.warning(
                        "[HEIMAN API] Token refresh loop: token already expired (expires_at=%s), refreshing now",
                        datetime.fromtimestamp(expires_at).isoformat() if expires_at else "unknown",
                    )
                else:
                    logger.info(
                        "[HEIMAN API] Token refresh loop: token expires in %.0fs, refreshing proactively",
                        remaining,
                    )

                refreshed = await self._try_refresh_token()
                if not refreshed:
                    logger.error(
                        "[HEIMAN API] Token refresh loop: refresh failed "
                        "(consecutive_failures=%d/%d)",
                        self._consecutive_failures, self._max_consecutive_failures,
                    )

            except asyncio.CancelledError:
                logger.info("[HEIMAN API] Token refresh loop cancelled")
                raise
            except Exception as e:
                logger.error("[HEIMAN API] Token refresh loop error: %s", e, exc_info=True)

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
            # 主动检查 token,避免 cache 刷新时 token 已过期导致 401
            await self._ensure_valid_token()
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

        try:
            result = await self._call_api_with_retry(
                self._heiman_client.get_home_list, user_id=self._user_id
            )

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
        except (HeimanAuthError, HeimanAPIError) as e:
            logger.error("[HEIMAN API] Get home list failed after retry: %s", e)
            return []
        except Exception as e:
            logger.error("[HEIMAN API] Get home list failed: %s", e)
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
            result = await self._heiman_client.get_home_detail(home_id=home_id)

            logger.info(
                "[HEIMAN API] get_home_detail for home %s: status=%s, result=%s",
                home_id,
                result.get("status"),
                str(result)[:1000],
            )

            if result.get("status") == 200:
                result_data = result.get("result", {})
                if isinstance(result_data, dict):
                    devices = result_data.get("deviceList", result_data.get("devices", []))
                    logger.info("[HEIMAN API] Found devices from home_detail: %d", len(devices))
                    if devices:
                        return devices
            
            logger.info("[HEIMAN API] Falling back to get_home_detail_post")
            try:
                result_post = await self._heiman_client.get_home_detail_post(home_id=home_id)
                logger.info("[HEIMAN API] get_home_detail_post for home %s: status=%s, result=%s", home_id, result_post.get("status"), str(result_post)[:1000])
                if result_post.get("status") == 200:
                    result_data = result_post.get("result", {})
                    if isinstance(result_data, dict):
                        devices = result_data.get("deviceList", result_data.get("devices", result_data.get("devList", [])))
                        if devices and isinstance(devices, list):
                            logger.info("[HEIMAN API] Found devices from home_detail_post: %d", len(devices))
                            if devices:
                                return devices
            except Exception as e:
                logger.warning("[HEIMAN API] get_home_detail_post failed: %s", e)
            
            logger.info("[HEIMAN API] Falling back to get_device_list")
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
                if devices:
                    return devices
            
            logger.info("[HEIMAN API] All API methods returned empty device list, trying database fallback")
            return await self._get_devices_from_db(home_id)
        except Exception as e:
            logger.error("[HEIMAN API] Get devices failed for home %s: %s", home_id, e)
            return await self._get_devices_from_db(home_id)
    
    async def _get_devices_from_db(self, home_id: str) -> list[dict]:
        try:
            from heiman.database.connector import get_db_connector
            
            db = get_db_connector()
            sql = """
                SELECT DISTINCT did, sensor_type, room_name, product_id 
                FROM sensor_logs 
                WHERE did IS NOT NULL AND did != '' 
                ORDER BY id DESC 
                LIMIT 50
            """
            results = db.execute_query(sql)
            
            devices = []
            seen_dids = set()
            for row in results:
                did = str(row.get("did", ""))
                if did and did not in seen_dids:
                    seen_dids.add(did)
                    device_info = {
                        "id": did,
                        "deviceId": did,
                        "name": did,
                        "deviceName": did,
                        "deviceType": {"value": "sensor"},
                        "roomId": "",
                        "roomName": row.get("room_name", ""),
                        "state": {"value": "online"},
                        "homeId": home_id,
                        "productId": row.get("product_id", ""),
                        "sensorType": row.get("sensor_type", ""),
                        "properties": {},
                        "deriveMetadata": [],
                    }
                    
                    props_sql = """
                        SELECT p.log_id, p.property_id, p.property_name, p.value, p.value_type, p.unit, s.timestamp
                        FROM sensor_log_properties p
                        JOIN sensor_logs s ON p.log_id = s.id
                        WHERE s.did = ?
                        ORDER BY s.timestamp DESC, p.property_id
                        LIMIT 20
                    """
                    props = db.execute_query(props_sql, (did,))
                    if props:
                        properties_dict = {}
                        derive_metadata = []
                        seen_props = set()
                        for prop in props:
                            prop_id = prop.get("property_id", "")
                            if prop_id in seen_props:
                                continue
                            seen_props.add(prop_id)
                            prop_value = prop.get("value", "")
                            try:
                                if prop_value.isdigit():
                                    properties_dict[prop_id] = int(prop_value)
                                elif '.' in prop_value:
                                    try:
                                        properties_dict[prop_id] = float(prop_value)
                                    except ValueError:
                                        properties_dict[prop_id] = prop_value
                                else:
                                    properties_dict[prop_id] = prop_value
                            except ValueError:
                                properties_dict[prop_id] = prop_value
                            
                            derive_metadata.append({
                                "property": prop_id,
                                "propertyName": prop.get("property_name", ""),
                                "value": prop_value,
                                "numberValue": int(prop_value) if prop_value.isdigit() else None,
                                "unit": prop.get("unit", ""),
                            })
                        device_info["properties"] = properties_dict
                        device_info["deriveMetadata"] = derive_metadata
                    
                    latest_log_sql = """
                        SELECT * FROM sensor_logs 
                        WHERE did = ? 
                        ORDER BY timestamp DESC 
                        LIMIT 1
                    """
                    latest_log = db.execute_query(latest_log_sql, (did,))
                    if latest_log:
                        log = latest_log[0]
                        for attr in ["battery", "rssi", "signal_level", "switch_state", "contact_state",
                                     "motion_state", "gas_state", "smoke_state", "water_state", 
                                     "alarm_state", "tamper_state", "temperature", "humidity"]:
                            val = log.get(attr)
                            if val is not None:
                                device_info[attr] = val
                    
                    if self._heiman_client:
                        try:
                            detail = await self._heiman_client.get_device_info(device_id=did)
                            if detail and detail.get("status") == 200:
                                result = detail.get("result", {})
                                if isinstance(result, dict):
                                    device_info.update({
                                        "name": result.get("name", did),
                                        "deviceName": result.get("deviceName", did),
                                        "productName": result.get("productName", ""),
                                        "photoUrl": result.get("photoUrl", ""),
                                        "parentId": result.get("parentId", ""),
                                        "deviceType": result.get("deviceType", {"value": "sensor"}),
                                        "state": result.get("state", {"value": "online"}),
                                        "roomId": result.get("roomId", ""),
                                        "roomName": result.get("roomName", row.get("room_name", "")),
                                    })
                                    api_derive_metadata = result.get("deriveMetadata")
                                    if api_derive_metadata and isinstance(api_derive_metadata, list) and len(api_derive_metadata) > 0:
                                        device_info["deriveMetadata"] = api_derive_metadata
                                    api_properties = result.get("properties")
                                    if api_properties and isinstance(api_properties, dict) and len(api_properties) > 0:
                                        device_info["properties"] = api_properties
                        except Exception as e:
                            logger.debug("[HEIMAN API] Failed to get device info for %s: %s", did, e)
                    
                    devices.append(device_info)
            
            logger.info("[HEIMAN API] Found %d devices from sensor_logs", len(devices))
            return devices
        except Exception as e:
            logger.warning("[HEIMAN API] Failed to get devices from database: %s", e)
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
                result_data = result.get("result", {})
                logs = result_data.get("data", result_data.get("list", []))
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
            alarm_info = log.get("alarmInfo", "")
            alarm_info_data = {}
            if alarm_info:
                try:
                    alarm_info_data = json.loads(alarm_info) if isinstance(alarm_info, str) else alarm_info
                except (json.JSONDecodeError, TypeError):
                    alarm_info_data = {}
            
            device_id = str(log.get("deviceId", log.get("sourceId", log.get("did", log.get("id", "")))))
            device = devices.get(device_id, {})
            device_name = log.get("deviceName", log.get("sourceName", log.get("name", alarm_info_data.get("deviceName", device.get("deviceName", device.get("name", ""))))))
            
            data_props = alarm_info_data.get("data", {})
            alarm_type_str = str(log.get("alarmType", log.get("type", ""))).lower()
            
            message = log.get("message", log.get("content", log.get("description", log.get("pushContent", ""))))
            if not message:
                alarm_name = log.get("alarmName", "")
                if alarm_name:
                    message = alarm_name
                elif data_props:
                    prop_messages = []
                    device_name_lower = str(device_name).lower() if device_name else ""
                    for prop_key, prop_val in data_props.items():
                        if prop_key == "SwitchState":
                            if "门磁" in device_name or "门窗" in device_name or "contact" in device_name_lower:
                                if prop_val == 0:
                                    prop_messages.append("门窗关闭")
                                elif prop_val == 1:
                                    prop_messages.append("门窗打开")
                                elif prop_val == 2:
                                    prop_messages.append("门窗关闭")
                                elif prop_val == 3:
                                    prop_messages.append("门窗打开")
                                else:
                                    prop_messages.append(f"门窗状态: {prop_val}")
                            elif "插座" in device_name or "plug" in device_name_lower:
                                if prop_val == 0:
                                    prop_messages.append("插座关闭")
                                elif prop_val == 1:
                                    prop_messages.append("插座开启")
                                elif prop_val == 2:
                                    prop_messages.append("插座关闭")
                                elif prop_val == 3:
                                    prop_messages.append("插座开启")
                                else:
                                    prop_messages.append(f"插座状态: {prop_val}")
                            else:
                                if prop_val == 0:
                                    prop_messages.append("设备关闭")
                                elif prop_val == 1:
                                    prop_messages.append("设备开启")
                                elif prop_val == 2:
                                    prop_messages.append("设备关闭")
                                elif prop_val == 3:
                                    prop_messages.append("设备开启")
                                else:
                                    prop_messages.append(f"开关状态: {prop_val}")
                        elif prop_key == "ContactState":
                            if prop_val == 0:
                                prop_messages.append("门窗关闭")
                            elif prop_val == 1:
                                prop_messages.append("门窗打开")
                            else:
                                prop_messages.append(f"门窗状态: {prop_val}")
                        elif prop_key == "MotionState":
                            if prop_val == 0:
                                prop_messages.append("无人移动")
                            elif prop_val == 1:
                                prop_messages.append("检测到移动")
                            else:
                                prop_messages.append(f"移动状态: {prop_val}")
                        elif prop_key == "SmokeSensorState":
                            if prop_val == 0:
                                prop_messages.append("烟雾正常")
                            elif prop_val == 1:
                                prop_messages.append("烟雾报警")
                            else:
                                prop_messages.append(f"烟雾状态: {prop_val}")
                        elif prop_key == "WaterSensorState":
                            if prop_val == 0:
                                prop_messages.append("水浸正常")
                            elif prop_val == 1:
                                prop_messages.append("水浸报警")
                            else:
                                prop_messages.append(f"水浸状态: {prop_val}")
                        elif prop_key == "GasSensorState":
                            if prop_val == 0:
                                prop_messages.append("燃气正常")
                            elif prop_val == 1:
                                prop_messages.append("燃气报警")
                            else:
                                prop_messages.append(f"燃气状态: {prop_val}")
                        else:
                            prop_messages.append(f"{prop_key}: {prop_val}")
                    message = "，".join(prop_messages) if prop_messages else "事件"
                else:
                    message = alarm_type_str or "事件"
            
            level = log.get("level", log.get("alarmLevel", ""))
            if isinstance(level, int):
                if level <= 2:
                    level = "high"
                elif level <= 4:
                    level = "warning"
                else:
                    level = "info"
            elif not level or level not in ["critical", "high", "medium", "low", "warning", "info"]:
                if "alarm" in alarm_type_str or "报警" in str(message):
                    level = "high"
                elif "warning" in alarm_type_str or "警告" in str(message):
                    level = "warning"
                elif "info" in alarm_type_str or "信息" in str(message) or "在线" in str(message) or "离线" in str(message):
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
            device_name_lower = str(device_name).lower()
            
            product_id = str(log.get("productId", device.get("productId", "")))
            
            if product_id == "heiman":
                try:
                    from heiman.database.connector import get_db_connector
                    db = get_db_connector()
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT product_id FROM sensor_logs WHERE did = ? ORDER BY id DESC LIMIT 1",
                            (device_id,)
                        )
                        row = cursor.fetchone()
                        if row and row[0]:
                            product_id = str(row[0])
                            logger.debug("[HEIMAN API] Resolved product_id from sensor_logs: %s -> %s", device_id, product_id)
                except Exception as e:
                    logger.debug("[HEIMAN API] Failed to resolve product_id from sensor_logs: %s", e)
            
            if "sensor_type" in log:
                sensor_type = str(log.get("sensor_type", "")).lower()
            
            if sensor_type is None or sensor_type == "":
                if product_id:
                    product_info = self._get_product_info(product_id)
                    if product_info:
                        db_product_name = product_info.get("name", "")
                        db_classified_name = product_info.get("classified_name", "")
                        if "门磁" in db_product_name or "门窗" in db_product_name:
                            sensor_type = SensorType.CONTACT.value
                        elif "插座" in db_product_name:
                            sensor_type = SensorType.PLUG.value
                        elif "contact" in db_product_name.lower():
                            sensor_type = SensorType.CONTACT.value
                        elif "plug" in db_product_name.lower():
                            sensor_type = SensorType.PLUG.value
                        else:
                            for keyword, st in PRODUCT_NAME_MAP:
                                if keyword.lower() in db_classified_name.lower() or keyword.lower() in db_product_name.lower():
                                    sensor_type = st.value
                                    break
            
            if sensor_type is None or sensor_type == "":
                for type_name, st in DEVICE_TYPE_MAP.items():
                    if type_name in device_name_lower:
                        sensor_type = st.value
                        break
            
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
                has_contact = "ContactState" in data_props
                has_switch = "SwitchState" in data_props
                if has_contact and has_switch:
                    if "门磁" in device_name or "门窗" in device_name:
                        sensor_type = SensorType.CONTACT.value
                    elif "插座" in device_name:
                        sensor_type = SensorType.PLUG.value
                    else:
                        sensor_type = SensorType.CONTACT.value
                elif has_contact:
                    sensor_type = SensorType.CONTACT.value
                elif has_switch:
                    sensor_type = SensorType.PLUG.value
                else:
                    for prop_key in data_props.keys():
                        if prop_key in PROPERTY_MAP:
                            sensor_type = PROPERTY_MAP[prop_key].value
                            break
            
            if sensor_type is None or sensor_type == "":
                sensor_type = "undefined"
            
            timestamp = log.get("timestamp", log.get("time", log.get("notifyTime", log.get("createTime", log.get("updatedTime", "")))))
            if not timestamp:
                timestamp = datetime.now().isoformat()
            elif isinstance(timestamp, (int, float)):
                if timestamp > 1e12:
                    timestamp = datetime.fromtimestamp(timestamp / 1000).isoformat()
                else:
                    timestamp = datetime.fromtimestamp(timestamp).isoformat()
            
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
        derive_metadata: list = []
        
        battery_value = None
        rssi_value = None
        signal_level = None
        contact_state = None
        tamper_state = None
        sensor_life_status = None
        alarm_state = None
        smoke_state = None
        gas_state = None
        water_state = None
        motion_state = None
        switch_state = None
        temp_value = None
        humidity_value = None
        co2_value = None
        pm25_value = None
        pm10_value = None
        hcho_value = None

        if product_id:
            product_info = self._get_product_info(product_id)
            if product_info:
                classified_name = product_info.get("classified_name", "")
                product_name = product_info.get("name", "")
                if "门磁" in product_name or "门窗" in product_name:
                    sensor_type = SensorType.CONTACT
                    unit = UNIT_MAP.get(sensor_type, "")
                elif "插座" in product_name:
                    sensor_type = SensorType.PLUG
                    unit = UNIT_MAP.get(sensor_type, "")
                else:
                    for keyword, sensor_type_enum in PRODUCT_NAME_MAP:
                        if keyword.lower() in classified_name.lower() or keyword.lower() in product_name.lower():
                            sensor_type = sensor_type_enum
                            unit = UNIT_MAP.get(sensor_type, "")
                            break

        properties = device.get("properties", {})
        has_contact_state = False
        has_switch_state = False
        has_motion_state = False
        
        if isinstance(properties, dict):
            for prop_id, prop_value in properties.items():
                if prop_id == "ContactState":
                    has_contact_state = True
                elif prop_id == "SwitchState":
                    has_switch_state = True
                elif prop_id == "MotionState" or prop_id == "OF" or prop_id == "DetectState":
                    has_motion_state = True
            
            for prop_id, prop_value in properties.items():
                if sensor_type is None and prop_id in PROPERTY_MAP:
                    sensor_type = PROPERTY_MAP[prop_id]
                    value = prop_value if prop_value is not None else 0
                    unit = UNIT_MAP.get(sensor_type, "")
                
                if prop_id == "BatteryPercentage":
                    battery_value = int(prop_value) if prop_value is not None else None
                elif prop_id == "GasSensorState":
                    gas_state = int(prop_value) if prop_value is not None else None
                elif prop_id == "SmokeSensorState":
                    smoke_state = int(prop_value) if prop_value is not None else None
                elif prop_id == "WaterSensorState":
                    water_state = int(prop_value) if prop_value is not None else None
                elif prop_id == "ContactState":
                    contact_state = int(prop_value) if prop_value is not None else None
                    if sensor_type == SensorType.CONTACT:
                        value = contact_state if contact_state is not None else 0
                    elif sensor_type is None:
                        sensor_type = SensorType.CONTACT
                        value = contact_state if contact_state is not None else 0
                        unit = UNIT_MAP.get(sensor_type, "")
                elif prop_id == "SwitchState":
                    switch_state = int(prop_value) if prop_value is not None else None
                    if sensor_type == SensorType.PLUG:
                        value = switch_state if switch_state is not None else 0
                    elif sensor_type == SensorType.CONTACT:
                        value = switch_state if switch_state is not None else 0
                    elif sensor_type is None:
                        if "门磁" in device_name or "门窗" in device_name:
                            sensor_type = SensorType.CONTACT
                            value = switch_state if switch_state is not None else 0
                            unit = UNIT_MAP.get(sensor_type, "")
                        else:
                            sensor_type = SensorType.PLUG
                            value = switch_state if switch_state is not None else 0
                            unit = UNIT_MAP.get(sensor_type, "")
                elif prop_id == "SignalLevel":
                    signal_level = int(prop_value) if prop_value is not None else None
                elif prop_id == "MotionState" or prop_id == "OF" or prop_id == "DetectState":
                    motion_state = int(prop_value) if prop_value is not None else None
                    if sensor_type == SensorType.MOTION:
                        value = motion_state if motion_state is not None else 0
                    elif sensor_type is None:
                        sensor_type = SensorType.MOTION
                        value = motion_state if motion_state is not None else 0
                        unit = UNIT_MAP.get(sensor_type, "")
                elif prop_id == "ALARM_STATE" or prop_id == "AlarmState":
                    alarm_state = int(prop_value) if prop_value is not None else None
                elif prop_id == "TamperState":
                    tamper_state = int(prop_value) if prop_value is not None else None
                elif prop_id == "SensorLifeStatus":
                    sensor_life_status = int(prop_value) if prop_value is not None else None
                elif prop_id == "CurrentTemperature":
                    temp_value = float(prop_value) if prop_value is not None else None
                elif prop_id == "CurrentHumidity":
                    humidity_value = float(prop_value) if prop_value is not None else None
                elif prop_id == "coValue" or prop_id == "CONC":
                    if sensor_type == SensorType.CO:
                        value = float(prop_value) if prop_value is not None else 0
        
        if sensor_type is not None:
            if has_contact_state and sensor_type == SensorType.PLUG:
                sensor_type = SensorType.CONTACT
                if contact_state is not None:
                    value = contact_state
                unit = UNIT_MAP.get(SensorType.CONTACT, "")
            elif has_motion_state and sensor_type == SensorType.PLUG:
                sensor_type = SensorType.MOTION
                if motion_state is not None:
                    value = motion_state
                unit = UNIT_MAP.get(SensorType.MOTION, "")

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
                                        value = float(prop_val) if prop_val is not None else 0
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
            state_value = state_info.get("value", "offline")
            if isinstance(state_value, str):
                is_online = state_value.lower() in ["online", "on", "1", "true"]
            elif isinstance(state_value, (int, float)):
                is_online = state_value != 0
            else:
                is_online = False
            state_update_time = state_info.get("updateTime") or state_info.get("time")
            logger.debug("[HEIMAN API] Device %s state_info: %s, is_online=%s", device_id, state_info, is_online)
        else:
            is_online = device.get("online", True)
            if isinstance(is_online, str):
                is_online = is_online.lower() in ["online", "on", "1", "true"]
            elif isinstance(is_online, (int, float)):
                is_online = is_online != 0
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

        for prop in derive_metadata:
            if isinstance(prop, dict):
                prop_id = prop.get("property", "")
                prop_val = prop.get("value")
                num_val = prop.get("numberValue")
                
                if prop_id == "BatteryPercentage":
                    battery_value = int(num_val) if num_val is not None else (int(prop_val) if prop_val is not None else None)
                elif prop_id == "GasSensorState":
                    gas_state = int(prop_val) if prop_val is not None else None
                elif prop_id == "SmokeSensorState":
                    smoke_state = int(prop_val) if prop_val is not None else None
                elif prop_id == "WaterSensorState":
                    water_state = int(prop_val) if prop_val is not None else None
                elif prop_id == "ContactState":
                    contact_state = int(prop_val) if prop_val is not None else None
                    if sensor_type == SensorType.CONTACT:
                        value = contact_state if contact_state is not None else 0
                elif prop_id == "SwitchState":
                    switch_state = int(prop_val) if prop_val is not None else None
                    if sensor_type == SensorType.PLUG:
                        value = switch_state if switch_state is not None else 0
                elif prop_id == "SignalLevel":
                    signal_level = int(prop_val) if prop_val is not None else None
                elif prop_id == "MotionState" or prop_id == "OF" or prop_id == "DetectState":
                    motion_state = int(prop_val) if prop_val is not None else None
                    if sensor_type == SensorType.MOTION:
                        value = motion_state if motion_state is not None else 0
                elif prop_id == "ALARM_STATE" or prop_id == "AlarmState":
                    alarm_state = int(prop_val) if prop_val is not None else None
                elif prop_id == "TamperState":
                    tamper_state = int(prop_val) if prop_val is not None else None
                elif prop_id == "SensorLifeStatus":
                    sensor_life_status = int(prop_val) if prop_val is not None else None
                elif prop_id == "CONC":
                    if sensor_type == SensorType.CO:
                        value = num_val if num_val is not None else (float(prop_val) if prop_val is not None else 0)
                elif prop_id == "coValue":
                    if sensor_type == SensorType.CO:
                        value = num_val if num_val is not None else (float(prop_val) if prop_val is not None else 0)
                elif prop_id == "CurrentTemperature":
                    temp_value = num_val if num_val is not None else (float(prop_val) if prop_val is not None else None)
                elif prop_id == "CurrentHumidity":
                    humidity_value = num_val if num_val is not None else (float(prop_val) if prop_val is not None else None)

        if battery_value is None:
            battery_value = device.get("battery")
        if rssi_value is None:
            rssi_value = device.get("rssi")
        if signal_level is None:
            signal_level = device.get("signalLevel")
        if contact_state is None:
            contact_state = device.get("contactState")
        if gas_state is None:
            gas_state = device.get("gasState")
        if smoke_state is None:
            smoke_state = device.get("smokeState")
        if water_state is None:
            water_state = device.get("waterState")
        if motion_state is None:
            motion_state = device.get("motionState")
        if switch_state is None:
            switch_state = device.get("switchState")
        if alarm_state is None:
            alarm_state = device.get("alarmState")
        if tamper_state is None:
            tamper_state = device.get("tamperState")
        if sensor_life_status is None:
            sensor_life_status = device.get("sensorLifeStatus")
        if temp_value is None:
            temp_value = device.get("temperature")
        if humidity_value is None:
            humidity_value = device.get("humidity")
        if co2_value is None:
            co2_value = device.get("co2")
        if pm25_value is None:
            pm25_value = device.get("pm25")
        if pm10_value is None:
            pm10_value = device.get("pm10")
        if hcho_value is None:
            hcho_value = device.get("hcho")

        if sensor_type == SensorType.CONTACT and contact_state is not None:
            value = contact_state
        elif sensor_type == SensorType.MOTION and motion_state is not None:
            value = motion_state
        elif sensor_type == SensorType.PLUG and switch_state is not None:
            value = switch_state

        return SensorData(
            did=device_id,
            name=device_name,
            sensor_type=sensor_type,
            product_id=product_id,
            value=value,
            unit=unit,
            status=status,
            room_id=room_id,
            room_name=room_name,
            home_id=home_id,
            icon=ICON_MAP.get(sensor_type),
            battery=battery_value,
            rssi=rssi_value,
            signalLevel=signal_level,
            contactState=contact_state,
            tamperState=tamper_state,
            sensorLifeStatus=sensor_life_status,
            alarmState=alarm_state,
            smokeState=smoke_state,
            gasState=gas_state,
            waterState=water_state,
            motionState=motion_state,
            switchState=switch_state,
            temperature=temp_value,
            humidity=humidity_value,
            co2=co2_value,
            pm25=pm25_value,
            pm10=pm10_value,
            hcho=hcho_value,
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

        if sensor_type == SensorType.SMOKE:
            if value == 1:
                return SensorStatus.ALARM
        elif sensor_type == SensorType.WATER:
            if value == 1:
                return SensorStatus.ALARM
        elif sensor_type == SensorType.CO:
            if int(value) >= 100:
                return SensorStatus.ALARM
            elif int(value) > 0:
                return SensorStatus.WARNING
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
        elif sensor_type == SensorType.CONTACT:
            if value == 2:
                return SensorStatus.ALARM
            elif value == 1:
                return SensorStatus.WARNING
        elif sensor_type == SensorType.MOTION:
            if value == 1:
                return SensorStatus.WARNING
        elif sensor_type == SensorType.PLUG:
            if value == 2:
                return SensorStatus.ALARM
        elif sensor_type == SensorType.SIREN:
            if value == 1:
                return SensorStatus.ALARM

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

            result = await self._call_api_with_retry(
                self._heiman_client.get_room_list, home_id=home_id
            )

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
            result = await self._call_api_with_retry(
                self._heiman_client.get_home_user_list, home_id=home_id
            )

            logger.info(
                "[HEIMAN API] get_home_members for home %s: data=%s",
                home_id,
                result,
            )

            if result.get("status") == 200:
                members = result.get("result", [])
                if isinstance(members, dict):
                    members = members.get("list", [])
                if not isinstance(members, list):
                    members = []
                return members
            return []
        except Exception as e:
            logger.error(
                "[HEIMAN API] Get home members failed for home %s: %s", home_id, e
            )
            return []

    async def get_device_panel(self, product_id: str) -> dict:
        """获取设备面板信息.

        Args:
            product_id: 产品ID

        Returns:
            面板信息字典，包含 panelUrl 等字段
        """
        if not self._heiman_client:
            return {}

        try:
            settings = get_settings()
            logger.info(
                "[HEIMAN API] get_device_panel - app_id=%s, product_id=%s",
                settings.heiman.app_id,
                product_id,
            )

            result = await self._call_api_with_retry(
                self._heiman_client.get_panel_by_app_product,
                app_id=settings.heiman.app_id,
                id_list=[product_id],
            )

            logger.info(
                "[HEIMAN API] get_device_panel response for product %s: data=%s",
                product_id,
                str(result)[:500],
            )

            if result.get("status") == 200:
                result_data = result.get("result", result)
                if isinstance(result_data, dict) and result_data.get("data"):
                    return result_data.get("data", {})
                elif isinstance(result_data, list) and len(result_data) > 0:
                    return result_data[0]
                return result_data
            return result
        except Exception as e:
            logger.error("[HEIMAN API] Get device panel failed for product %s: %s", product_id, e)
            return {}

    async def prepare_panel_entry(self, panel_url: str, sync_data: dict | None = None) -> dict:
        """准备面板入口，创建文件系统会话.
        
        Args:
            panel_url: 面板 URL
            sync_data: 同步数据（语言、设备信息等）
            
        Returns:
            会话信息，包含 sessionId、entryUrl、fileCount
        """
        if not self._heiman_client:
            return {}

        try:
            if sync_data is None:
                sync_data = {}
            result = await self._heiman_client.prepare_panel_entry(panel_url, sync_data)

            logger.info(
                "[HEIMAN API] prepare_panel_entry: panel_url=%s, result=%s",
                panel_url,
                str(result)[:500],
            )

            return result
        except Exception as e:
            logger.error("[HEIMAN API] Prepare panel entry failed: %s", e)
            return {}

    async def close_panel_session(self, session_id: str) -> dict:
        """关闭面板会话.
        
        Args:
            session_id: 会话 ID
            
        Returns:
            关闭结果
        """
        if not self._heiman_client:
            return {}

        try:
            result = await self._heiman_client.close_panel_session(session_id)

            logger.info(
                "[HEIMAN API] close_panel_session: session_id=%s, result=%s",
                session_id,
                str(result)[:200],
            )

            return result
        except Exception as e:
            logger.error("[HEIMAN API] Close panel session failed for %s: %s", session_id, e)
            return {}