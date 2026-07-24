import logging
import uuid
from datetime import datetime
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from httpx import AsyncClient

from heiman.config import get_settings
from heiman.shared_state import get_oauth_state_store, get_current_token, set_current_token
from heiman_mcp.client.heiman import HeimanClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_oauth_state_store = get_oauth_state_store()


class HomeSelectRequest(BaseModel):
    home_id: str


def get_oauth_token() -> dict | None:
    """Get current OAuth token if available."""
    return get_current_token()


@router.get("/login")
async def login():
    settings = get_settings()
    state = str(uuid.uuid4())
    _oauth_state_store[state] = {"created_at": datetime.now()}

    authorize_url = (
        f"{settings.heiman.authorize_url}"
        f"?client_id={settings.heiman.client_id}"
        f"&redirect_uri={settings.heiman.redirect_uri}"
        f"&response_type=code"
        f"&state={state}"
    )

    logger.info("[AUTH] OAuth2 authorize redirect: state=%s, url=%s", state, authorize_url)
    return RedirectResponse(url=authorize_url)


@router.post("/login")
async def login_post():
    settings = get_settings()
    state = str(uuid.uuid4())
    _oauth_state_store[state] = {"created_at": datetime.now()}

    authorize_url = (
        f"{settings.heiman.authorize_url}"
        f"?client_id={settings.heiman.client_id}"
        f"&redirect_uri={settings.heiman.redirect_uri}"
        f"&response_type=code"
        f"&state={state}"
    )

    return {"authorize_url": authorize_url, "state": state}


@router.get("/heiman_redirect")
async def heiman_redirect(code: str, state: str):
    settings = get_settings()

    if state not in _oauth_state_store:
        logger.warning("[AUTH] Invalid state parameter: %s", state)
        raise HTTPException(status_code=400, detail="Invalid state")

    del _oauth_state_store[state]

    logger.info("[AUTH] Exchanging code for token")

    try:
        # 使用 HeimanClient 的 OAuth2 方法获取 token
        # 注意：海曼 API 使用自签名证书，需要禁用 SSL 验证
        oauth_client = HeimanClient(base_url=settings.heiman.api_url, token=None)
        token_data = await oauth_client.exchange_code_for_token(
            code=code,
            redirect_uri=settings.heiman.redirect_uri,
            client_id=settings.heiman.client_id,
            client_secret=settings.heiman.client_secret,
        )
        await oauth_client.close()

        logger.info(
            "[AUTH] Token response: %s",
            {k: v if k != "access_token" else f"***({len(v)} chars)" for k, v in token_data.items()},
        )

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")

        if not access_token:
            logger.error("[AUTH] No access token in response: %s", token_data)
            raise HTTPException(status_code=400, detail="No access token in response")

        logger.info("[AUTH] OAuth2 token obtained successfully, expires_in=%s", token_data.get("expires_in"))

        # 使用 token 获取用户信息
        user_client = HeimanClient(
            base_url=settings.heiman.api_url,
            token=access_token,
        )
        try:
            user_info = await user_client.get_current_user()
            logger.info(
                "[AUTH] User info response type: %s, content: %s",
                type(user_info).__name__,
                str(user_info)[:500] if user_info else "None",
            )

            user_id = ""
            if user_info and isinstance(user_info, dict):
                result = user_info.get("result")
                if result and isinstance(result, dict):
                    user_id = str(result.get("id", ""))
                elif "id" in user_info:
                    user_id = str(user_info.get("id"))

            if not user_id:
                logger.warning("[AUTH] User info response has no 'id', generating fallback user_id")
                user_id = f"user_{int(datetime.now().timestamp())}"
        except Exception as user_error:
            logger.warning("[AUTH] Failed to get user info: %s, generating fallback user_id", user_error)
            user_id = f"user_{int(datetime.now().timestamp())}"
        finally:
            await user_client.close()

        logger.info("[AUTH] User info verified: user_id=%s", user_id)

        set_current_token({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": datetime.now().timestamp() + (token_data.get("expires_in", 3600)),
            "user_id": user_id,
        })

        logger.info("[AUTH] Token stored, user_id=%s", user_id)

        try:
            from heiman.manager import get_manager
            mgr = get_manager()

            # 用户重新登录,重置 token 刷新状态(清除之前的失败计数和冷却时间)
            mgr.api_client.reset_refresh_state()

            login_success = await mgr.api_client.login_with_oauth_token(access_token, user_id)

            if login_success:
                try:
                    await mgr.adapter.sync_devices()
                    await mgr.adapter.refresh_sensor_data()
                    logger.info("[AUTH] API client initialized with OAuth token")
                except Exception as sync_error:
                    logger.warning("[AUTH] Device sync failed: %s, continuing", sync_error)

                try:
                    from heiman.mqtt_service import get_mqtt_service
                    mqtt_service = get_mqtt_service()
                    logger.info("[AUTH] Attempting MQTT connection with access_token=%s, user_id=%s", 
                                access_token[:20] if access_token else "None", user_id)
                    mqtt_connected = await mqtt_service.connect(access_token, user_id, force=True)
                    if mqtt_connected:
                        logger.info("[AUTH] MQTT service connected successfully with SSL/TLS")
                    else:
                        logger.warning("[AUTH] MQTT service connection failed, continuing without MQTT")
                except Exception as e:
                    logger.error("[AUTH] Failed to initialize MQTT service: %s", e, exc_info=True)
            else:
                logger.warning("[AUTH] API client login failed, continuing without full initialization")

        except Exception as e:
            logger.warning("[AUTH] Service initialization partially failed: %s, continuing with limited functionality", e)

        return RedirectResponse(url="/dashboard", status_code=302)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[AUTH] Token exchange failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Token exchange failed: {e}")


@router.get("/token")
async def get_token():
    token_info = get_current_token()
    if not token_info:
        return {
            "success": True,
            "data": {
                "authenticated": False,
                "user_id": "",
            },
        }

    access_token = token_info.get("access_token")
    user_id = token_info.get("user_id", "")

    async def try_mqtt_connect():
        try:
            from heiman.mqtt_service import get_mqtt_service
            mqtt_service = get_mqtt_service()
            if not mqtt_service.is_connected and access_token and user_id:
                logger.info("[AUTH] MQTT not connected, attempting async connection")
                mqtt_connected = await mqtt_service.connect(access_token, user_id)
                if mqtt_connected:
                    logger.info("[AUTH] MQTT service connected successfully")
                else:
                    logger.warning("[AUTH] MQTT service connection failed")
        except Exception as e:
            logger.error("[AUTH] Failed to initialize MQTT service: %s", e)

    import asyncio
    asyncio.create_task(try_mqtt_connect())

    return {
        "success": True,
        "data": {
            "authenticated": True,
            "user_id": user_id,
        },
    }


@router.post("/refresh")
async def refresh_token(body: dict | None = None):
    settings = get_settings()
    stored_token = get_current_token()

    # 优先使用前端请求体中的 refresh_token,回退到后端存储的
    request_refresh_token = body.get("refresh_token") if body else None
    stored_refresh_token = stored_token.get("refresh_token") if stored_token else None
    refresh_token_to_use = request_refresh_token or stored_refresh_token

    if not refresh_token_to_use:
        raise HTTPException(status_code=401, detail="No refresh token available")

    logger.info("[AUTH] Refreshing token (source=%s)", "request_body" if request_refresh_token else "stored")

    try:
        oauth_client = HeimanClient(base_url=settings.heiman.api_url, token=None)
        token_data = await oauth_client.refresh_access_token(
            refresh_token=refresh_token_to_use,
            client_id=settings.heiman.client_id,
            client_secret=settings.heiman.client_secret,
        )
        await oauth_client.close()

        logger.info(
            "[AUTH] Refresh token response type: %s, content: %s",
            type(token_data).__name__,
            str(token_data)[:800],
        )

        if isinstance(token_data, dict):
            status = token_data.get("status")
            result = token_data.get("result")
            message = token_data.get("message", "")

            # 兼容两种响应格式:
            # 1. 扁平结构(OAuth2 标准): {"access_token":"xxx","refresh_token":"xxx","expires_in":3600}
            # 2. 嵌套结构(Heiman 业务包装): {"status":200,"result":{"access_token":"xxx",...}}
            access_token = token_data.get("access_token")
            refresh_token_new = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)

            if not access_token and isinstance(result, dict):
                logger.info("[AUTH] Trying nested result field for token data")
                access_token = result.get("access_token")
                refresh_token_new = result.get("refresh_token") or refresh_token_new
                expires_in = result.get("expires_in", expires_in)

            if not access_token:
                logger.error(
                    "[AUTH] No access token in refresh response: status=%s, message=%s, "
                    "result=%s, keys=%s. Keeping existing token.",
                    status, message,
                    str(result)[:200] if result else None,
                    list(token_data.keys()),
                )
                # 不清除已有 token,让用户仍可使用旧 token(若未过期)
                raise HTTPException(
                    status_code=401,
                    detail="Refresh token invalid, please re-authenticate"
                )
        else:
            logger.error("[AUTH] Token refresh returned unexpected response type: %s", type(token_data).__name__)
            raise HTTPException(status_code=500, detail="Token refresh failed")

        set_current_token({
            "access_token": access_token,
            "refresh_token": refresh_token_new or refresh_token_to_use,
            "expires_at": datetime.now().timestamp() + expires_in,
            "user_id": stored_token.get("user_id", "") if stored_token else "",
        })

        logger.info("[AUTH] OAuth2 token refreshed successfully")

        user_id = stored_token.get("user_id", "") if stored_token else ""
        if user_id:
            try:
                from heiman.manager import get_manager
                mgr = get_manager()
                await mgr.api_client.login_with_oauth_token(access_token, user_id)
                logger.info("[AUTH] API client token updated after refresh")
            except Exception as e:
                logger.error("[AUTH] Failed to update API client token after refresh: %s", e)

            try:
                from heiman.mqtt_service import get_mqtt_service
                mqtt_service = get_mqtt_service()
                if not mqtt_service.is_connected:
                    await mqtt_service.connect(access_token, user_id)
                    logger.info("[AUTH] MQTT reconnected after token refresh (was disconnected)")
                else:
                    mqtt_service.update_token(access_token)
                    logger.info("[AUTH] MQTT token updated after refresh (connection kept alive)")
            except Exception as e:
                logger.error("[AUTH] Failed to update MQTT token after refresh: %s", e)

        return {
            "success": True,
            "data": {
                "access_token": access_token,
                "refresh_token": refresh_token_new,
                "token_type": "bearer",
                "expires_in": expires_in,
                "expires_at": datetime.now().timestamp() + expires_in,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[AUTH] Token refresh failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {e}")


@router.get("/me")
async def get_me():
    try:
        from heiman.manager import get_manager
        mgr = get_manager()

        user_info = await mgr.api_client.get_user_info()
        token_info = get_current_token()

        if user_info:
            access_token = token_info.get("access_token", "") if token_info else ""
            logger.info("[AUTH] Get me success for user: %s", user_info.get("nickName", user_info.get("userName", "")))
            return {
                "success": True,
                "data": {
                    "userId": str(user_info.get("id", "")),
                    "username": user_info.get("nickName") or user_info.get("userName") or "",
                    "nickName": user_info.get("nickName") or "",
                    "email": user_info.get("email") or "",
                    "phone": user_info.get("phone") or "",
                    "avatar": user_info.get("headImgUrl") or "",
                    "bindStatus": True,
                    "accessToken": access_token,
                },
            }
        else:
            logger.warning("[AUTH] Get me failed: no user info")
            return {
                "success": False,
                "data": None,
                "message": "Not authenticated",
            }
    except Exception as e:
        logger.error("[AUTH] Get me failed: %s", e)
        return {"success": False, "data": None, "message": str(e)}


@router.get("/profile")
async def get_profile():
    try:
        from heiman.manager import get_manager
        mgr = get_manager()

        user_info = await mgr.api_client.get_user_info()
        token_info = get_current_token()

        if user_info:
            access_token = token_info.get("access_token", "") if token_info else ""
            logger.info("[AUTH] Get profile success for user: %s", user_info.get("nickName", user_info.get("userName", "")))
            return {
                "success": True,
                "data": {
                    "userId": str(user_info.get("id", "")),
                    "username": user_info.get("nickName") or user_info.get("userName") or "",
                    "nickName": user_info.get("nickName") or "",
                    "email": user_info.get("email") or "",
                    "phone": user_info.get("phone") or "",
                    "avatar": user_info.get("headImgUrl") or "",
                    "bindStatus": True,
                    "accessToken": access_token,
                },
            }
        else:
            logger.warning("[AUTH] Get profile failed: no user info")
            return {
                "success": False,
                "data": None,
                "message": "Not authenticated",
            }
    except Exception as e:
        logger.error("[AUTH] Get profile failed: %s", e)
        return {"success": False, "data": None, "message": str(e)}


def get_current_access_token() -> str:
    token_info = _oauth_state_store.get("current_token")
    if not token_info:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if datetime.now().timestamp() > token_info["expires_at"]:
        raise HTTPException(status_code=401, detail="Token expired")

    return token_info["access_token"]


@router.post("/verify_token")
async def verify_token(token: dict, authorization: str | None = None):
    settings = get_settings()
    access_token = token.get("token") or (authorization or "").replace("bearer ", "")

    logger.info("[AUTH] Token verification requested, token_length=%d", len(access_token) if access_token else 0)

    if not access_token:
        logger.warning("[AUTH] No token provided for verification")
        raise HTTPException(status_code=400, detail="No token provided")

    try:
        async with AsyncClient(verify=False) as client:
            headers = {
                "Authorization": f"bearer {access_token}",
                "Tenant-Id": settings.heiman.tenant_id,
                "Accept-Language": settings.heiman.language,
            }
            user_info_response = await client.get(
                f"{settings.heiman.api_url}/api-app/appUser/current/user",
                headers=headers,
            )

            logger.info("[AUTH] User info verification status: %d", user_info_response.status_code)

            if user_info_response.status_code == 200:
                user_info = user_info_response.json()
                user_id = str(user_info.get("result", {}).get("id", ""))

                logger.info("[AUTH] Token verified successfully, user_id=%s", user_id)

                set_current_token({
                    "access_token": access_token,
                    "expires_at": datetime.now().timestamp() + 3600,
                    "user_id": user_id,
                })

                try:
                    from heiman.manager import get_manager
                    mgr = get_manager()

                    login_success = await mgr.api_client.login_with_oauth_token(access_token, user_id)

                    if login_success:
                        await mgr.adapter.sync_devices()
                        await mgr.adapter.refresh_sensor_data()
                        logger.info("[AUTH] API client initialized with verified token")

                        try:
                            from heiman.mqtt_service import get_mqtt_service
                            mqtt_service = get_mqtt_service()
                            mqtt_connected = await mqtt_service.connect(access_token, user_id)
                            if mqtt_connected:
                                logger.info("[AUTH] MQTT service connected successfully with SSL/TLS after token verification")
                            else:
                                logger.warning("[AUTH] MQTT service connection failed after token verification")
                        except Exception as e:
                            logger.error("[AUTH] Failed to initialize MQTT service: %s", e)
                    else:
                        logger.warning("[AUTH] API client login failed after token verification")
                except Exception as e:
                    logger.error("[AUTH] Failed to initialize services with verified token: %s", e)

                return {
                    "success": True,
                    "message": "Token verified successfully",
                    "user_id": user_id,
                }
            else:
                logger.warning("[AUTH] Token verification failed, status=%d", user_info_response.status_code)
                raise HTTPException(status_code=401, detail="Invalid token")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[AUTH] Token verification error: %s", e)
        raise HTTPException(status_code=500, detail=f"Token verification failed: {e}")


@router.post("/home-select")
async def save_home_selection(request: HomeSelectRequest):
    token_info = get_current_token()
    if not token_info:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = token_info.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    home_id = request.home_id
    from heiman.shared_state import set_last_home
    success = set_last_home(user_id, home_id)

    if success:
        logger.info("[AUTH] Home selection saved: user_id=%s, home_id=%s", user_id, home_id)
        return {"success": True, "message": "Home selection saved"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save home selection")


@router.get("/last-home")
async def get_last_home_selection():
    token_info = get_current_token()
    if not token_info:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = token_info.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    from heiman.shared_state import get_last_home
    home_id = get_last_home(user_id)

    return {"success": True, "data": {"home_id": home_id}}


@router.post("/logout")
async def logout():
    """退出登录:清除存储的 token、断开 MQTT、重置 API client。

    这是唯一会删除 token 的入口,refresh 失败时不会删除 token。
    """
    token_info = get_current_token()
    user_id = token_info.get("user_id", "") if token_info else ""

    logger.info("[AUTH] Logout requested, user_id=%s", user_id)

    # 1. 清除存储的 token(内存 + DB)
    set_current_token(None)

    # 2. 断开 MQTT 连接
    try:
        from heiman.mqtt_service import get_mqtt_service
        mqtt_service = get_mqtt_service()
        if mqtt_service.is_connected:
            await mqtt_service.disconnect()
            logger.info("[AUTH] MQTT disconnected on logout")
    except Exception as e:
        logger.warning("[AUTH] Failed to disconnect MQTT on logout: %s", e)

    # 3. 重置 API client 状态
    try:
        from heiman.manager import get_manager
        mgr = get_manager()
        mgr.api_client.reset_refresh_state()
        mgr.api_client._cleanup()
        logger.info("[AUTH] API client cleaned up on logout")
    except Exception as e:
        logger.warning("[AUTH] Failed to cleanup API client on logout: %s", e)

    return {"success": True, "data": {"message": "Logged out successfully"}}