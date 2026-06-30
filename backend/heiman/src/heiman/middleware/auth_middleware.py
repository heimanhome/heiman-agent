import logging

from fastapi import Request

from heiman.config import get_settings
from heiman.middleware.exceptions import AuthenticationException
from heiman.shared_state import get_current_token

logger = logging.getLogger(__name__)

BEARER_PREFIX = "bearer "

WHITELIST_PATHS = [
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/token",
    "/api/auth/verify_token",
    "/api/auth/heiman_redirect",
    "/api/auth/profile",
    "/api/auth/home-select",
    "/api/auth/last-home",
    "/api/health",
]


def _extract_bearer_token(authorization: str | None) -> str | None:
    if authorization:
        auth_lower = authorization.lower()
        if auth_lower.startswith(BEARER_PREFIX):
            return authorization[len(BEARER_PREFIX) :]
    return None


def _is_whitelisted(path: str) -> bool:
    for prefix in WHITELIST_PATHS:
        if path.startswith(prefix):
            return True
    return False


def verify_token(request: Request) -> None:
    service_token = get_settings().server.token
    if not service_token:
        return

    if _is_whitelisted(request.url.path):
        return

    authorization_header = request.headers.get("Authorization")
    token = _extract_bearer_token(authorization_header)
    
    if token == service_token:
        return

    current_token = get_current_token()
    if current_token and token == current_token.get("access_token"):
        return

    logger.warning(
        "Auth failed: path=%s has_token=%s",
        request.url.path,
        token is not None,
    )
    raise AuthenticationException("Invalid or missing service token")


def verify_token_query_fallback(request: Request) -> None:
    service_token = get_settings().server.token
    if not service_token:
        return

    if _is_whitelisted(request.url.path):
        return

    token = (
        _extract_bearer_token(request.headers.get("Authorization"))
        or request.query_params.get("token")
    )
    if token != service_token:
        logger.warning(
            "Auth failed (query fallback): path=%s has_token=%s",
            request.url.path,
            token is not None,
        )
        raise AuthenticationException("Invalid or missing service token")