import logging
import sqlite3
from typing import Any

from heiman.database.connector import get_db_connector

logger = logging.getLogger(__name__)


class KVRepo:
    def __init__(self):
        self.db_connector = get_db_connector()
        self.cache = {}
        self._init_cache()

    def _init_cache(self):
        for attempt in range(3):
            try:
                self.cache = self.get_all_as_dict()
                logger.info("[DB] KVRepo init, keys: %s", list(self.cache.keys()))
                return
            except Exception as e:
                logger.warning("[DB] KVRepo init attempt %d failed: %s", attempt + 1, e)
                if attempt < 2:
                    import time
                    time.sleep(0.5)
        logger.error("[DB] KVRepo init failed after 3 attempts")

    def set(self, key: str, value: str) -> bool:
        try:
            current_time = int(__import__("time").time() * 1000)
            sql = """
                INSERT INTO kv (key, value, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
            """
            params = (key, value, current_time, current_time)
            affected_rows = self.db_connector.execute_update(sql, params)
            if affected_rows > 0:
                self.cache[key] = value
                logger.info("[DB] KV set successfully: key=%s", key)
                return True
            else:
                logger.warning("[DB] Failed to set kv: key=%s", key)
                return False
        except (ValueError, TypeError, KeyError, AttributeError, sqlite3.Error) as e:
            logger.error("[DB] Error setting kv: key=%s, error=%s", key, e)
            return False

    def _get_by_key(self, key: str) -> dict[str, Any] | None:
        try:
            sql = "SELECT * FROM kv WHERE key = ?"
            params = (key,)
            results = self.db_connector.execute_query(sql, params)
            if results:
                logger.debug("[DB] KV found: key=%s", key)
                return results[0]
            else:
                logger.debug("[DB] KV not found: key=%s", key)
                return None
        except (ValueError, TypeError, KeyError, AttributeError, sqlite3.Error) as e:
            logger.error("[DB] Error querying kv: key=%s, error=%s", key, e)
            return None

    def get(self, key: str, default_value: str | None = None) -> str | None:
        if key in self.cache:
            return self.cache[key]
        kv = self._get_by_key(key)
        if kv:
            return kv.get("value")
        return default_value

    def get_all(self) -> dict[str, str]:
        return self.cache

    def get_all_as_dict(self) -> dict[str, str]:
        try:
            all_kvs = self._get_all()
            kv_dict = {}

            for kv in all_kvs:
                key = kv.get("key")
                value = kv.get("value")
                if key is not None and value is not None:
                    kv_dict[key] = value
            logger.info("[DB] Retrieved %d kv as dict", len(kv_dict))
            return kv_dict
        except (ValueError, TypeError, KeyError, AttributeError, sqlite3.Error) as e:
            logger.error("[DB] Error converting kv to dict: error=%s", e)
            return {}

    def _get_all(self) -> list[dict[str, Any]]:
        try:
            sql = "SELECT * FROM kv ORDER BY key"
            results = self.db_connector.execute_query(sql)
            logger.debug("[DB] Retrieved %d kv items", len(results))
            return results
        except (ValueError, TypeError, KeyError, AttributeError, sqlite3.Error) as e:
            logger.error("[DB] Error retrieving all kv: error=%s", e)
            return []

    def delete(self, key: str) -> bool:
        try:
            sql = "DELETE FROM kv WHERE key = ?"
            params = (key,)
            affected_rows = self.db_connector.execute_update(sql, params)

            if affected_rows > 0:
                self.cache.pop(key, None)
                logger.info("[DB] KV deleted successfully: key=%s", key)
                return True
            else:
                logger.debug("[DB] KV key not found, skip delete: key=%s", key)
                return False

        except (ValueError, TypeError, KeyError, AttributeError, sqlite3.Error) as e:
            logger.error("[DB] Error deleting kv: key=%s, error=%s", key, e)
            return False

    def exists(self, key: str) -> bool:
        try:
            if key in self.cache:
                return True
            sql = "SELECT COUNT(*) as count FROM kv WHERE key = ?"
            params = (key,)
            results = self.db_connector.execute_query(sql, params)

            if results and results[0]["count"] > 0:
                return True
            return False

        except (ValueError, TypeError, KeyError, AttributeError, sqlite3.Error) as e:
            logger.error("[DB] Error checking kv existence: key=%s, error=%s", key, e)
            return False


class AuthConfigKeys:
    HEIMAN_TOKEN_INFO_KEY = "HEIMAN_TOKEN_INFO_KEY"


class SystemConfigKeys:
    DEVICE_UUID_KEY = "DEVICE_UUID_KEY"


class DeviceInfoKeys:
    USER_INFO_KEY = "USER_INFO_KEY"


class ScopeConfigKeys:
    HOME_WHITE_LIST_KEY = "HOME_WHITE_LIST_KEY"
    DEVICE_BLACK_LIST_KEY = "DEVICE_BLACK_LIST_KEY"


_kv_repo_instance = None


def get_kv_repo() -> KVRepo:
    global _kv_repo_instance
    if _kv_repo_instance is None:
        _kv_repo_instance = KVRepo()
    return _kv_repo_instance