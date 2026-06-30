import logging
from typing import Optional
from datetime import datetime

from heiman.database.connector import get_db_connector

logger = logging.getLogger(__name__)


class SystemLogRepo:
    def __init__(self):
        self._db = get_db_connector()

    def insert(self, level: str, action: str, user: str, message: str) -> None:
        try:
            now = datetime.now()
            self._db.execute_update(
                """
                INSERT INTO system_logs (time, level, action, user, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (now.strftime("%Y-%m-%d %H:%M:%S"), level, action, user, message),
            )
            logger.info("[LOG] Inserted system log: level=%s, action=%s, user=%s", level, action, user)
        except Exception as e:
            logger.error("[LOG] Failed to insert system log: %s", e)
            raise

    def query(
        self,
        level: Optional[str] = None,
        action: Optional[str] = None,
        user: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        try:
            query = "SELECT * FROM system_logs WHERE 1=1"
            params: tuple = ()

            if level:
                query += " AND level = ?"
                params += (level,)
            if action:
                query += " AND action LIKE ?"
                params += (f"%{action}%",)
            if user:
                query += " AND user LIKE ?"
                params += (f"%{user}%",)
            if search:
                query += " AND (message LIKE ? OR action LIKE ? OR user LIKE ?)"
                search_pattern = f"%{search}%"
                params += (search_pattern, search_pattern, search_pattern)

            query += " ORDER BY time DESC LIMIT ?"
            params += (limit,)

            rows = self._db.execute_query(query, params)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("[LOG] Failed to query system logs: %s", e)
            raise

    def get_error_logs(self, search: Optional[str] = None, limit: int = 100) -> list[dict]:
        return self.query(level="error", search=search, limit=limit)

    def get_operation_logs(self, search: Optional[str] = None, limit: int = 100) -> list[dict]:
        return self.query(search=search, limit=limit)

    def get_by_id(self, log_id: int) -> Optional[dict]:
        try:
            rows = self._db.execute_query(
                "SELECT * FROM system_logs WHERE id = ?",
                (log_id,),
            )
            return dict(rows[0]) if rows else None
        except Exception as e:
            logger.error("[LOG] Failed to get log by id: %s", e)
            raise

    def count(self, level: Optional[str] = None) -> int:
        try:
            query = "SELECT COUNT(*) as count FROM system_logs WHERE 1=1"
            params: tuple = ()

            if level:
                query += " AND level = ?"
                params += (level,)

            rows = self._db.execute_query(query, params)
            return rows[0]["count"] if rows else 0
        except Exception as e:
            logger.error("[LOG] Failed to count logs: %s", e)
            raise


_log_repo = None


def get_log_repo() -> SystemLogRepo:
    global _log_repo
    if _log_repo is None:
        _log_repo = SystemLogRepo()
    return _log_repo
