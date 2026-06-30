import json
import logging

from heiman.database.kv_repo import get_kv_repo

logger = logging.getLogger(__name__)

TOKEN_KEY = "heiman_oauth_token"
LAST_HOME_KEY_PREFIX = "heiman_last_home_"

_oauth_state_store: dict[str, dict] = {}


def get_oauth_state_store() -> dict[str, dict]:
    return _oauth_state_store


def get_current_token() -> dict | None:
    token = _oauth_state_store.get("current_token")
    if token:
        return token
    
    return load_token_from_db()


def set_current_token(token: dict | None) -> None:
    if token:
        _oauth_state_store["current_token"] = token
        _persist_token(token)
    else:
        _oauth_state_store.pop("current_token", None)
        _clear_token()


def _persist_token(token: dict) -> None:
    try:
        kv_repo = get_kv_repo()
        kv_repo.set(TOKEN_KEY, json.dumps(token))
        logger.info("[STATE] OAuth token persisted to database")
    except Exception as e:
        logger.error("[STATE] Failed to persist OAuth token: %s", e)


def _clear_token() -> None:
    try:
        kv_repo = get_kv_repo()
        kv_repo.delete(TOKEN_KEY)
        logger.info("[STATE] OAuth token cleared from database")
    except Exception as e:
        logger.error("[STATE] Failed to clear OAuth token: %s", e)


def load_token_from_db() -> dict | None:
    try:
        kv_repo = get_kv_repo()
        token_str = kv_repo.get(TOKEN_KEY)
        if token_str:
            token = json.loads(token_str)
            _oauth_state_store["current_token"] = token
            logger.info("[STATE] OAuth token loaded from database")
            return token
        return None
    except Exception as e:
        logger.error("[STATE] Failed to load OAuth token from database: %s", e)
        return None


def get_last_home(user_id: str) -> str | None:
    try:
        kv_repo = get_kv_repo()
        return kv_repo.get(f"{LAST_HOME_KEY_PREFIX}{user_id}")
    except Exception as e:
        logger.error("[STATE] Failed to get last home for user %s: %s", user_id, e)
        return None


def set_last_home(user_id: str, home_id: str) -> bool:
    try:
        kv_repo = get_kv_repo()
        return kv_repo.set(f"{LAST_HOME_KEY_PREFIX}{user_id}", home_id)
    except Exception as e:
        logger.error("[STATE] Failed to set last home for user %s: %s", user_id, e)
        return False