"""task_record rollover 调度。

每日 0:05 (Asia/Shanghai) 触发：扫 progress / duration 主表所有
recurring + 活跃行，按 window 边界（day/week/month）判断今天是否到点，
到点则调 TaskRecordService.rollover_one 完成 archive + insert new。
"""
import json
import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from heiman.database.task_record_repo import TaskRecordRepo
from heiman.schema.task import RecordKind

logger = logging.getLogger(__name__)


def _to_aware(dt: datetime) -> datetime:
    """naive datetime 按本地时区解读补 tzinfo，aware 保持不变。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt


def _parse_iso_aware(s) -> datetime:
    """ISO 字符串 → aware datetime;int 视为 Unix ms。"""
    from datetime import timezone

    if isinstance(s, int):
        return datetime.fromtimestamp(s / 1000, tz=timezone.utc).astimezone(
            datetime.now().astimezone().tzinfo
        )
    return _to_aware(datetime.fromisoformat(s.replace("Z", "+00:00")))


def _parse_pattern(pattern: str | None) -> dict[str, Any] | None:
    if not pattern:
        return None
    try:
        loaded = json.loads(pattern)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _window_period_start(window: str, now: datetime) -> datetime:
    """该 window 当前 period 的起点（与 now 同时区——naive 进 naive 出）。"""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if window == "day":
        return midnight
    if window == "week":
        return midnight - timedelta(days=now.weekday())
    if window == "month":
        return midnight.replace(day=1)
    return datetime.min.replace(tzinfo=now.tzinfo)


def _should_rollover(
    row: sqlite3.Row,
    kind: RecordKind,
    now: datetime,
    prev_archived_at: str | None,
) -> bool:
    """判断 task 是否需要在本次 daily job 跑 rollover。"""
    pattern = _parse_pattern(row["recurring_pattern"])
    if pattern is None:
        return False
    if kind is RecordKind.PROGRESS:
        window = row["window"]
    else:
        window = pattern.get("window", "day")
    if window == "longterm":
        return False

    now_aware = _to_aware(now)
    period_start = _window_period_start(window, now_aware)
    prev_period_end = period_start - timedelta(seconds=1)

    if prev_archived_at is None:
        try:
            created_dt = _parse_iso_aware(row["created_at"])
        except ValueError:
            return True
        return created_dt < period_start

    try:
        prev_dt = _parse_iso_aware(prev_archived_at)
    except ValueError:
        return True
    return prev_dt < prev_period_end


def _last_archived_at(
    cursor: sqlite3.Cursor, table: str, task_id: str
) -> str | None:
    row = cursor.execute(
        f"SELECT MAX(archived_at) AS ts FROM {table} "
        "WHERE task_id = ? AND archived_at IS NOT NULL",
        (task_id,),
    ).fetchone()
    return row["ts"] if row and row["ts"] is not None else None


def rollover_daily_job(
    repo: TaskRecordRepo,
    now: datetime | None = None,
) -> dict[str, int]:
    """扫所有 recurring + 到边界的 progress / duration 活跃行做 rollover。"""
    now_dt = now or datetime.now()
    counts = {"progress": 0, "duration": 0, "skipped": 0, "failed": 0}

    progress_rows = repo.list_recurring_active(RecordKind.PROGRESS)
    duration_rows = repo.list_recurring_active(RecordKind.DURATION)

    for row in progress_rows:
        task_id = row["task_id"]
        prev = repo.last_archived_at(task_id, "task_record_progress")
        if not _should_rollover(row, RecordKind.PROGRESS, now_dt, prev):
            counts["skipped"] += 1
            continue
        try:
            repo.rollover_one(task_id, RecordKind.PROGRESS)
            counts["progress"] += 1
        except Exception as e:
            logger.error("Progress rollover failed for %s: %s", task_id, e)
            counts["failed"] += 1

    for row in duration_rows:
        task_id = row["task_id"]
        prev = repo.last_archived_at(task_id, "task_record_duration")
        if not _should_rollover(row, RecordKind.DURATION, now_dt, prev):
            counts["skipped"] += 1
            continue
        try:
            repo.rollover_one(task_id, RecordKind.DURATION)
            counts["duration"] += 1
        except Exception as e:
            logger.error("Duration rollover failed for %s: %s", task_id, e)
            counts["failed"] += 1

    logger.info("Rollover daily job done: %s", counts)
    return counts


def seconds_until_next_run(now: datetime, hour: int = 0, minute: int = 5) -> float:
    """到下一个 HH:MM 时刻的秒数（用于 daily loop sleep）。"""
    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return (next_run - now).total_seconds()