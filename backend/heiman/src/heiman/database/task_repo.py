import logging
import sqlite3
from datetime import datetime
from typing import Any

from heiman.database.connector import get_db_connector

logger = logging.getLogger(__name__)


class TaskLinkConflict(Exception):
    pass


class TaskRepo:
    def __init__(self):
        self.db = get_db_connector()

    def create_task(self, task_id: str, description: str) -> None:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                now = datetime.now().isoformat()
                cursor.execute(
                    "INSERT INTO task (task_id, description, status, created_at, updated_at) "
                    "VALUES (?, ?, 'active', ?, ?)",
                    (task_id, description, now, now),
                )
                conn.commit()
                logger.info("Task created (placeholder): task_id=%s", task_id)
            except sqlite3.IntegrityError as e:
                conn.rollback()
                msg = str(e)
                if "task.task_id" in msg or "UNIQUE" in msg:
                    raise TaskLinkConflict(f"task_id {task_id!r} 已存在") from e
                raise

    def add_link(self, task_id: str, kind: str, ref: str) -> None:
        if kind not in ("rule", "cron"):
            raise TaskLinkConflict(
                f"link_kind {kind!r} 不合法，仅支持 rule / cron"
            )
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO task_link "
                    "(task_id, link_kind, link_ref) VALUES (?, ?, ?)",
                    (task_id, kind, ref),
                )
                conn.commit()
            except sqlite3.IntegrityError as e:
                msg = str(e)
                if "FOREIGN KEY" in msg:
                    raise TaskLinkConflict(
                        f"task {task_id!r} 不存在,先调 task create"
                    ) from e
                raise TaskLinkConflict(
                    f"{kind} ref {ref!r} 撞库（已挂在其它 task 或重复添加）"
                ) from e

    def task_exists(self, task_id: str) -> bool:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM task WHERE task_id = ?", (task_id,)
            ).fetchone()
            return row is not None

    def get_full_view(self, task_id: str) -> dict[str, Any] | None:
        with self.db.get_connection() as conn:
            task_row = conn.execute(
                "SELECT task_id, description, status, paused_at, created_at "
                "FROM task WHERE task_id=?",
                (task_id,),
            ).fetchone()
            if task_row is None:
                return None
            links = conn.execute(
                "SELECT link_kind AS kind, link_ref AS ref FROM task_link "
                "WHERE task_id=?",
                (task_id,),
            ).fetchall()
            return {
                "task_id": task_row["task_id"],
                "description": task_row["description"],
                "status": task_row["status"],
                "paused_at": task_row["paused_at"],
                "created_at": task_row["created_at"],
                "links": [{"kind": link["kind"], "ref": link["ref"]} for link in links],
            }

    def list_all(self) -> list[dict[str, Any]]:
        with self.db.get_connection() as conn:
            tasks = conn.execute(
                "SELECT task_id, description, status, paused_at, created_at "
                "FROM task ORDER BY created_at DESC"
            ).fetchall()
            all_links = conn.execute(
                "SELECT task_id, link_kind AS kind, link_ref AS ref FROM task_link"
            ).fetchall()
            links_by_task: dict[str, list[dict]] = {}
            for link in all_links:
                links_by_task.setdefault(link["task_id"], []).append(
                    {"kind": link["kind"], "ref": link["ref"]}
                )
            return [
                {
                    "task_id": t["task_id"],
                    "description": t["description"],
                    "status": t["status"],
                    "paused_at": t["paused_at"],
                    "created_at": t["created_at"],
                    "links": links_by_task.get(t["task_id"], []),
                }
                for t in tasks
            ]

    def set_status(self, task_id: str, status: str) -> str:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            current = cursor.execute(
                "SELECT status FROM task WHERE task_id=?", (task_id,)
            ).fetchone()
            if current is None:
                return "not_found"
            if current["status"] == status:
                return "noop"
            paused_at = datetime.now().isoformat() if status == "paused" else None
            now = datetime.now().isoformat()
            cursor.execute(
                "UPDATE task SET status=?, paused_at=?, updated_at=? WHERE task_id=?",
                (status, paused_at, now, task_id),
            )
            conn.commit()
            return "ok"

    def update_description(self, task_id: str, description: str) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                "UPDATE task SET description=?, updated_at=? WHERE task_id=?",
                (description, now, task_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_task(self, task_id: str) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM task WHERE task_id=?", (task_id,))
            conn.commit()
            return cursor.rowcount

    def get_rule_refs(self, task_id: str) -> list[str]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT link_ref FROM task_link "
                "WHERE task_id=? AND link_kind='rule'",
                (task_id,),
            ).fetchall()
            return [r["link_ref"] for r in rows]

    def delete_link_by_ref(self, kind: str, ref: str) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM task_link WHERE link_kind=? AND link_ref=?",
                (kind, ref),
            )
            conn.commit()
            return cursor.rowcount
