"""Token usage repository - track API token consumption."""

import logging
from datetime import datetime, date, timedelta
from typing import Optional

from heiman.database.connector import get_db_connector

logger = logging.getLogger(__name__)


class TokenUsageRepo:
    """Repository for token usage tracking."""

    def __init__(self):
        self.db = get_db_connector()
        self._ensure_table()

    def _ensure_table(self) -> None:
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS token_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp_ms INTEGER NOT NULL,
                        model TEXT NOT NULL DEFAULT '',
                        usage_type TEXT NOT NULL DEFAULT 'api',
                        prompt_tokens INTEGER NOT NULL DEFAULT 0,
                        completion_tokens INTEGER NOT NULL DEFAULT 0,
                        total_tokens INTEGER NOT NULL DEFAULT 0,
                        endpoint TEXT DEFAULT '',
                        user_id TEXT DEFAULT ''
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS token_usage_daily (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        model TEXT NOT NULL DEFAULT '',
                        usage_type TEXT NOT NULL DEFAULT 'api',
                        prompt_tokens INTEGER NOT NULL DEFAULT 0,
                        completion_tokens INTEGER NOT NULL DEFAULT 0,
                        total_tokens INTEGER NOT NULL DEFAULT 0,
                        request_count INTEGER NOT NULL DEFAULT 0,
                        UNIQUE(date, model, usage_type)
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp 
                    ON token_usage(timestamp_ms)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_token_usage_model 
                    ON token_usage(model)
                """)
                conn.commit()
        except Exception as e:
            logger.error("[DB] Failed to ensure token_usage tables: %s", e)
            raise

    def record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        usage_type: str = "api",
        endpoint: str = "",
        user_id: str = "",
    ) -> None:
        try:
            timestamp_ms = int(datetime.now().timestamp() * 1000)
            total_tokens = prompt_tokens + completion_tokens

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO token_usage (
                        timestamp_ms, model, usage_type, prompt_tokens,
                        completion_tokens, total_tokens, endpoint, user_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp_ms, model, usage_type, prompt_tokens,
                    completion_tokens, total_tokens, endpoint, user_id,
                ))
                conn.commit()

            logger.debug(
                "[DB] Token usage recorded: model=%s, total=%d, type=%s",
                model, total_tokens, usage_type
            )
        except Exception as e:
            logger.error("[DB] Failed to record token usage: %s", e)
            raise

    def list_events(
        self,
        since_ms: Optional[int] = None,
        until_ms: Optional[int] = None,
        limit: int = 10000,
    ) -> tuple[list[dict], bool]:
        try:
            query = "SELECT * FROM token_usage WHERE 1=1"
            params: list = []

            if since_ms:
                query += " AND timestamp_ms >= ?"
                params.append(since_ms)
            else:
                today_start = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                query += " AND timestamp_ms >= ?"
                params.append(int(today_start.timestamp() * 1000))

            if until_ms:
                query += " AND timestamp_ms <= ?"
                params.append(until_ms)

            query += " ORDER BY timestamp_ms DESC LIMIT ?"
            params.append(limit + 1)

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()

            truncated = len(rows) > limit
            if truncated:
                rows = rows[:limit]

            events = [dict(row) for row in rows]
            return events, truncated
        except Exception as e:
            logger.error("[DB] Failed to list token usage events: %s", e)
            raise

    def aggregate_daily(
        self,
        since_date: Optional[str] = None,
        until_date: Optional[str] = None,
    ) -> list[dict]:
        try:
            if not since_date:
                since = date.today() - timedelta(days=30)
                since_date = since.isoformat()
            if not until_date:
                until_date = date.today().isoformat()

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT date, model, usage_type,
                           SUM(prompt_tokens) as prompt_tokens,
                           SUM(completion_tokens) as completion_tokens,
                           SUM(total_tokens) as total_tokens,
                           SUM(request_count) as request_count
                    FROM token_usage_daily
                    WHERE date >= ? AND date <= ?
                    GROUP BY date, model, usage_type
                    ORDER BY date DESC, model, usage_type
                """, (since_date, until_date))
                rows = cursor.fetchall()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("[DB] Failed to aggregate daily token usage: %s", e)
            raise

    def aggregate_buckets(
        self,
        since_ms: Optional[int] = None,
        until_ms: Optional[int] = None,
        bin_minutes: int = 60,
    ) -> list[dict]:
        try:
            if not since_ms:
                today_start = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                since_ms = int(today_start.timestamp() * 1000)
            if not until_ms:
                until_ms = int(datetime.now().timestamp() * 1000)

            bin_ms = bin_minutes * 60 * 1000

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        (timestamp_ms / ?) * ? as bucket_start,
                        model,
                        usage_type,
                        SUM(prompt_tokens) as prompt_tokens,
                        SUM(completion_tokens) as completion_tokens,
                        SUM(total_tokens) as total_tokens,
                        COUNT(*) as request_count
                    FROM token_usage
                    WHERE timestamp_ms >= ? AND timestamp_ms <= ?
                    GROUP BY bucket_start, model, usage_type
                    ORDER BY bucket_start DESC, model, usage_type
                """, (bin_ms, bin_ms, since_ms, until_ms))
                rows = cursor.fetchall()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("[DB] Failed to aggregate token usage buckets: %s", e)
            raise

    def clear_all(self) -> dict[str, int]:
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM token_usage")
                deleted_realtime = cursor.rowcount
                cursor.execute("DELETE FROM token_usage_daily")
                deleted_daily = cursor.rowcount
                conn.commit()

            logger.info(
                "[DB] Cleared token usage: realtime=%d, daily=%d",
                deleted_realtime, deleted_daily
            )
            return {
                "token_usage": deleted_realtime,
                "token_usage_daily": deleted_daily,
            }
        except Exception as e:
            logger.error("[DB] Failed to clear token usage: %s", e)
            raise

    def rollup_daily(self, target_date: Optional[date] = None) -> None:
        if not target_date:
            target_date = date.today() - timedelta(days=1)

        date_str = target_date.isoformat()
        day_start = int(datetime.combine(target_date, datetime.min.time()).timestamp() * 1000)
        day_end = day_start + 86400000 - 1

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT model, usage_type,
                           SUM(prompt_tokens) as prompt_tokens,
                           SUM(completion_tokens) as completion_tokens,
                           SUM(total_tokens) as total_tokens,
                           COUNT(*) as request_count
                    FROM token_usage
                    WHERE timestamp_ms >= ? AND timestamp_ms <= ?
                    GROUP BY model, usage_type
                """, (day_start, day_end))
                rows = cursor.fetchall()

                for row in rows:
                    cursor.execute("""
                        INSERT OR REPLACE INTO token_usage_daily (
                            date, model, usage_type, prompt_tokens,
                            completion_tokens, total_tokens, request_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        date_str,
                        row["model"],
                        row["usage_type"],
                        row["prompt_tokens"],
                        row["completion_tokens"],
                        row["total_tokens"],
                        row["request_count"],
                    ))

                conn.commit()

            logger.info("[DB] Daily token rollup completed for %s", date_str)
        except Exception as e:
            logger.error("[DB] Failed to rollup daily token usage: %s", e)


_token_usage_repo_instance = None


def get_token_usage_repo() -> TokenUsageRepo:
    global _token_usage_repo_instance
    if _token_usage_repo_instance is None:
        _token_usage_repo_instance = TokenUsageRepo()
    return _token_usage_repo_instance
