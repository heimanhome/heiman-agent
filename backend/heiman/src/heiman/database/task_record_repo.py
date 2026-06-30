import logging
from datetime import datetime, timedelta
from typing import Any

from heiman.database.connector import get_db_connector
from heiman.schema.task import (
    RecordKind,
    RecordStatus,
    ProgressWindow,
    DerivedProgress,
    DerivedDuration,
    DerivedEvent,
)

logger = logging.getLogger(__name__)


class TaskRecordRepo:
    def __init__(self):
        self.db = get_db_connector()

    def init_progress_record(self, task_id: str, target: int, unit: str, window: ProgressWindow, recurring_pattern: str | None = None) -> None:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO task_record_progress (task_id, target, current, unit, window, status, recurring_pattern, created_at, updated_at) "
                "VALUES (?, ?, 0, ?, ?, 'active', ?, ?, ?)",
                (task_id, target, unit, window.value, recurring_pattern, now, now),
            )
            conn.commit()
            logger.info("Progress record initialized: task_id=%s", task_id)

    def init_duration_record(self, task_id: str, target_minutes: int | None = None, recurring_pattern: str | None = None) -> None:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO task_record_duration (task_id, target_minutes, status, recurring_pattern, created_at, updated_at) "
                "VALUES (?, ?, 'active', ?, ?, ?)",
                (task_id, target_minutes, recurring_pattern, now, now),
            )
            conn.commit()
            logger.info("Duration record initialized: task_id=%s", task_id)

    def init_event_record(self, task_id: str, recurring_pattern: str | None = None) -> None:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO task_record_event (task_id, status, recurring_pattern, created_at, updated_at) "
                "VALUES (?, 'active', ?, ?, ?)",
                (task_id, recurring_pattern, now, now),
            )
            conn.commit()
            logger.info("Event record initialized: task_id=%s", task_id)

    def increment_progress(self, task_id: str, delta: int = 1) -> tuple[int, int, str]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT current, target, status FROM task_record_progress WHERE task_id=?",
                (task_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Progress record not found for task_id={task_id}")

            new_current = row["current"] + delta
            status = row["status"]
            if new_current >= row["target"] and status == "active":
                status = "completed"

            now = datetime.now().isoformat()
            cursor.execute(
                "UPDATE task_record_progress SET current=?, status=?, updated_at=? WHERE task_id=?",
                (new_current, status, now, task_id),
            )
            conn.commit()
            return new_current, row["target"], status

    def get_progress_derived(self, task_id: str) -> DerivedProgress | None:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT current, target FROM task_record_progress WHERE task_id=?",
                (task_id,),
            ).fetchone()
            if not row:
                return None
            remaining = max(0, row["target"] - row["current"])
            progress_pct = (row["current"] / row["target"] * 100) if row["target"] > 0 else 0.0
            return DerivedProgress(
                remaining=remaining,
                progress_pct=round(progress_pct, 1),
            )

    def start_session(self, task_id: str) -> tuple[str, bool, str]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT active_session_start_at, status FROM task_record_duration WHERE task_id=?",
                (task_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Duration record not found for task_id={task_id}")

            if row["active_session_start_at"]:
                return row["active_session_start_at"], True, row["status"]

            now = datetime.now().isoformat()
            cursor.execute(
                "UPDATE task_record_duration SET active_session_start_at=?, updated_at=? WHERE task_id=?",
                (now, now, task_id),
            )
            conn.commit()
            return now, False, row["status"]

    def end_session(self, task_id: str) -> tuple[int, str]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT active_session_start_at, status, target_minutes FROM task_record_duration WHERE task_id=?",
                (task_id,),
            ).fetchone()
            if not row or not row["active_session_start_at"]:
                raise ValueError(f"No active session for task_id={task_id}")

            start_at = row["active_session_start_at"]
            end_at = datetime.now()
            start_dt = datetime.fromisoformat(start_at)
            duration_seconds = int((end_at - start_dt).total_seconds())
            this_session_minutes = duration_seconds // 60

            now = end_at.isoformat()
            cursor.execute(
                "INSERT INTO task_duration_session (task_id, start_at, end_at, duration_seconds) "
                "VALUES (?, ?, ?, ?)",
                (task_id, start_at, now, duration_seconds),
            )

            status = row["status"]
            target_minutes = row["target_minutes"]
            if target_minutes and status == "active":
                total_minutes = self._get_total_minutes(conn, task_id)
                if total_minutes >= target_minutes:
                    status = "completed"

            cursor.execute(
                "UPDATE task_record_duration SET active_session_start_at=NULL, status=?, updated_at=? WHERE task_id=?",
                (status, now, task_id),
            )
            conn.commit()
            return this_session_minutes, status

    def _get_total_minutes(self, conn, task_id: str) -> int:
        row = conn.execute(
            "SELECT COALESCE(SUM(duration_seconds), 0) as total FROM task_duration_session WHERE task_id=?",
            (task_id,),
        ).fetchone()
        return row["total"] // 60 if row else 0

    def get_duration_derived(self, task_id: str) -> DerivedDuration | None:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT active_session_start_at, target_minutes FROM task_record_duration WHERE task_id=?",
                (task_id,),
            ).fetchone()
            if not row:
                return None

            total_seconds = self._get_total_seconds_today(conn, task_id)
            accumulated_minutes_today = total_seconds // 60

            remaining_minutes = None
            if row["target_minutes"]:
                remaining_minutes = max(0, row["target_minutes"] - accumulated_minutes_today)

            return DerivedDuration(
                accumulated_minutes_today=accumulated_minutes_today,
                remaining_minutes=remaining_minutes,
                active_session_start_at=row["active_session_start_at"],
            )

    def _get_total_seconds_today(self, conn, task_id: str) -> int:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        row = conn.execute(
            "SELECT COALESCE(SUM(duration_seconds), 0) as total FROM task_duration_session "
            "WHERE task_id=? AND start_at >= ?",
            (task_id, today_start),
        ).fetchone()
        return row["total"] if row else 0

    def append_event(self, task_id: str, description: str, at: str | None = None) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            now = at or datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO task_event_entry (task_id, description, at) VALUES (?, ?, ?)",
                (task_id, description, now),
            )
            cursor.execute(
                "UPDATE task_record_event SET updated_at=? WHERE task_id=?",
                (datetime.now().isoformat(), task_id),
            )
            conn.commit()
            return cursor.lastrowid

    def get_event_derived(self, task_id: str) -> DerivedEvent | None:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM task_record_event WHERE task_id=?",
                (task_id,),
            ).fetchone()
            if not row:
                return None

            total_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM task_event_entry WHERE task_id=?",
                (task_id,),
            ).fetchone()
            count_total = total_row["cnt"] if total_row else 0

            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            today_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM task_event_entry WHERE task_id=? AND at >= ?",
                (task_id, today_start),
            ).fetchone()
            count_today = today_row["cnt"] if today_row else 0

            last_row = conn.execute(
                "SELECT at FROM task_event_entry WHERE task_id=? ORDER BY at DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            last_at = last_row["at"] if last_row else None

            return DerivedEvent(
                count_total=count_total,
                count_today=count_today,
                last_at=last_at,
            )

    def get_record_kind(self, task_id: str) -> RecordKind | None:
        with self.db.get_connection() as conn:
            for kind, table in [
                (RecordKind.PROGRESS, "task_record_progress"),
                (RecordKind.DURATION, "task_record_duration"),
                (RecordKind.EVENT, "task_record_event"),
            ]:
                row = conn.execute(
                    f"SELECT 1 FROM {table} WHERE task_id=?",
                    (task_id,),
                ).fetchone()
                if row:
                    return kind
        return None

    def record_exists(self, task_id: str) -> bool:
        return self.get_record_kind(task_id) is not None

    def get_base_record(self, task_id: str, kind: RecordKind) -> dict | None:
        """Get base record data for a task."""
        with self.db.get_connection() as conn:
            conn.row_factory = self.db._dict_factory
            table_map = {
                RecordKind.PROGRESS: "task_record_progress",
                RecordKind.DURATION: "task_record_duration",
                RecordKind.EVENT: "task_record_event",
            }
            table = table_map.get(kind)
            if not table:
                return None
            row = conn.execute(
                f"SELECT * FROM {table} WHERE task_id=?",
                (task_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_recent_sessions(self, task_id: str, limit: int = 10) -> list[dict]:
        """Get recent duration sessions."""
        with self.db.get_connection() as conn:
            conn.row_factory = self.db._dict_factory
            rows = conn.execute(
                """SELECT * FROM task_duration_session 
                   WHERE task_id=? ORDER BY start_at DESC LIMIT ?""",
                (task_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recent_events(self, task_id: str, limit: int = 50) -> list[dict]:
        """Get recent events."""
        with self.db.get_connection() as conn:
            conn.row_factory = self.db._dict_factory
            rows = conn.execute(
                """SELECT * FROM task_event_entry 
                   WHERE task_id=? ORDER BY at DESC LIMIT ?""",
                (task_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_progress_history(self, task_id: str) -> list[dict]:
        """Get progress history (daily aggregates)."""
        with self.db.get_connection() as conn:
            conn.row_factory = self.db._dict_factory
            rows = conn.execute(
                """SELECT date(start_at) as day, COUNT(*) as count
                   FROM task_duration_session
                   WHERE task_id=?
                   GROUP BY day ORDER BY day DESC LIMIT 30""",
                (task_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_duration_weekly(self, task_id: str) -> list[dict]:
        """Get weekly duration aggregates."""
        with self.db.get_connection() as conn:
            conn.row_factory = self.db._dict_factory
            rows = conn.execute(
                """SELECT 
                       strftime('%Y-W%W', start_at) as week,
                       COALESCE(SUM(duration_seconds), 0) as total_seconds,
                       COUNT(*) as session_count
                   FROM task_duration_session
                   WHERE task_id=?
                   GROUP BY week ORDER BY week DESC LIMIT 12""",
                (task_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_duration_daily(self, task_id: str) -> list[dict]:
        """Get daily duration aggregates."""
        with self.db.get_connection() as conn:
            conn.row_factory = self.db._dict_factory
            rows = conn.execute(
                """SELECT 
                       date(start_at) as day,
                       COALESCE(SUM(duration_seconds), 0) as total_seconds,
                       COUNT(*) as session_count
                   FROM task_duration_session
                   WHERE task_id=?
                   GROUP BY day ORDER BY day DESC LIMIT 30""",
                (task_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_events_by_day(self, task_id: str) -> list[dict]:
        """Get events aggregated by day."""
        with self.db.get_connection() as conn:
            conn.row_factory = self.db._dict_factory
            rows = conn.execute(
                """SELECT date(at) as day, COUNT(*) as count
                   FROM task_event_entry
                   WHERE task_id=?
                   GROUP BY day ORDER BY day DESC LIMIT 30""",
                (task_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_archives(self, task_id: str, limit: int = 30, offset: int = 0) -> list[dict]:
        """List archived records (placeholder - currently returns completed records)."""
        kind = self.get_record_kind(task_id)
        if not kind:
            return []

        with self.db.get_connection() as conn:
            conn.row_factory = self.db._dict_factory
            table_map = {
                RecordKind.PROGRESS: "task_record_progress",
                RecordKind.DURATION: "task_record_duration",
                RecordKind.EVENT: "task_record_event",
            }
            table = table_map.get(kind)
            if not table:
                return []
            rows = conn.execute(
                f"""SELECT * FROM {table} 
                    WHERE task_id=? AND status='completed'
                    ORDER BY updated_at DESC LIMIT ? OFFSET ?""",
                (task_id, limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_recurring_active(self, kind: RecordKind) -> list[dict]:
        """List all recurring + active records for a given kind."""
        with self.db.get_connection() as conn:
            conn.row_factory = self.db._dict_factory
            table_map = {
                RecordKind.PROGRESS: "task_record_progress",
                RecordKind.DURATION: "task_record_duration",
                RecordKind.EVENT: "task_record_event",
            }
            table = table_map.get(kind)
            if not table:
                return []
            rows = conn.execute(
                f"""SELECT * FROM {table} 
                    WHERE recurring_pattern IS NOT NULL AND status='active'""",
            ).fetchall()
            return [dict(r) for r in rows]

    def last_archived_at(self, task_id: str, table: str) -> str | None:
        """Get the last archived_at timestamp for a task in the given table."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                f"SELECT MAX(archived_at) AS ts FROM {table} "
                "WHERE task_id = ? AND archived_at IS NOT NULL",
                (task_id,),
            ).fetchone()
            return row["ts"] if row and row["ts"] is not None else None

    def rollover_one(self, task_id: str, kind: RecordKind) -> None:
        """Archive current record and create new one for the next period."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            table_map = {
                RecordKind.PROGRESS: "task_record_progress",
                RecordKind.DURATION: "task_record_duration",
                RecordKind.EVENT: "task_record_event",
            }
            table = table_map.get(kind)
            if not table:
                return

            row = conn.execute(
                f"SELECT * FROM {table} WHERE task_id=? AND status='active'",
                (task_id,),
            ).fetchone()
            if not row:
                return

            cursor.execute(
                f"UPDATE {table} SET status='completed', archived_at=?, updated_at=? WHERE task_id=?",
                (now, now, task_id),
            )

            if kind == RecordKind.PROGRESS:
                cursor.execute(
                    "INSERT INTO task_record_progress "
                    "(task_id, target, current, unit, window, recurring_pattern, status, created_at, updated_at) "
                    "VALUES (?, ?, 0, ?, ?, ?, 'active', ?, ?)",
                    (task_id, row["target"], row["unit"], row["window"], row["recurring_pattern"], now, now),
                )
            elif kind == RecordKind.DURATION:
                cursor.execute(
                    "INSERT INTO task_record_duration "
                    "(task_id, target_minutes, recurring_pattern, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'active', ?, ?)",
                    (task_id, row["target_minutes"], row["recurring_pattern"], now, now),
                )
            elif kind == RecordKind.EVENT:
                cursor.execute(
                    "INSERT INTO task_record_event "
                    "(task_id, recurring_pattern, status, created_at, updated_at) "
                    "VALUES (?, ?, 'active', ?, ?)",
                    (task_id, row["recurring_pattern"], now, now),
                )

            conn.commit()
            logger.info("Rollover completed for task_id=%s kind=%s", task_id, kind.value)
