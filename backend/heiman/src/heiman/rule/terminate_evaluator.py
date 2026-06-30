"""Rule terminate evaluator - evaluate if a rule task should be terminated."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from heiman.schema.task import TerminateReason

logger = logging.getLogger(__name__)


class TerminateEvaluator:
    """Evaluates termination conditions for rules and tasks."""

    def __init__(self):
        self._task_completion_cache: dict[str, dict[str, Any]] = {}

    def evaluate_progress_termination(
        self,
        task_id: str,
        current: int,
        target: int,
    ) -> tuple[bool, TerminateReason | None]:
        """Evaluate if a progress task should be terminated.

        Returns:
            Tuple of (should_terminate, reason)
        """
        if current >= target:
            logger.info(
                "Progress task completed: task_id=%s, current=%d, target=%d",
                task_id, current, target,
            )
            return True, TerminateReason.COMPLETED

        return False, None

    def evaluate_duration_termination(
        self,
        task_id: str,
        accumulated_minutes: int,
        target_minutes: int | None = None,
    ) -> tuple[bool, TerminateReason | None]:
        """Evaluate if a duration task should be terminated."""
        if target_minutes and accumulated_minutes >= target_minutes:
            logger.info(
                "Duration task completed: task_id=%s, accumulated=%d min, target=%d min",
                task_id, accumulated_minutes, target_minutes,
            )
            return True, TerminateReason.COMPLETED

        return False, None

    def evaluate_rule_termination(
        self,
        rule_id: str,
        trigger_count: int,
        max_triggers: int | None = None,
        start_time: datetime | None = None,
        duration_hours: int | None = None,
    ) -> tuple[bool, TerminateReason | None]:
        """Evaluate if a rule should be auto-terminated."""
        if max_triggers and trigger_count >= max_triggers:
            logger.info(
                "Rule max triggers reached: rule_id=%s, count=%d, max=%d",
                rule_id, trigger_count, max_triggers,
            )
            return True, TerminateReason.COMPLETED

        if start_time and duration_hours:
            elapsed = datetime.now() - start_time
            if elapsed >= timedelta(hours=duration_hours):
                logger.info(
                    "Rule duration expired: rule_id=%s, elapsed=%.1fh, duration=%dh",
                    rule_id, elapsed.total_seconds() / 3600, duration_hours,
                )
                return True, TerminateReason.EXPIRED

        return False, None

    def should_auto_disable_rule(
        self,
        rule_id: str,
        consecutive_failures: int,
        max_failures: int = 10,
    ) -> bool:
        """Check if a rule should be auto-disabled due to failures."""
        if consecutive_failures >= max_failures:
            logger.warning(
                "Rule should be auto-disabled: rule_id=%s, failures=%d, max=%d",
                rule_id, consecutive_failures, max_failures,
            )
            return True
        return False

    def evaluate_task_completion(
        self,
        task_id: str,
        kind: str,
        record_data: dict[str, Any],
    ) -> tuple[bool, TerminateReason | None]:
        """Generic task completion evaluation."""
        if kind == "progress":
            current = record_data.get("current", 0)
            target = record_data.get("target", 0)
            if target > 0 and current >= target:
                return True, TerminateReason.COMPLETED

        elif kind == "duration":
            target_minutes = record_data.get("target_minutes")
            accumulated = record_data.get("accumulated_minutes_today", 0)
            if target_minutes and accumulated >= target_minutes:
                return True, TerminateReason.COMPLETED

        return False, None

    def get_completion_summary(
        self,
        task_id: str,
        kind: str,
        record_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Get a summary of task completion status."""
        completed = False
        progress = 0.0
        reason = None

        if kind == "progress":
            current = record_data.get("current", 0)
            target = record_data.get("target", 0)
            if target > 0:
                progress = min(100.0, (current / target) * 100)
                if current >= target:
                    completed = True
                    reason = TerminateReason.COMPLETED.value

        elif kind == "duration":
            target_minutes = record_data.get("target_minutes")
            accumulated = record_data.get("accumulated_minutes_today", 0)
            if target_minutes and target_minutes > 0:
                progress = min(100.0, (accumulated / target_minutes) * 100)
                if accumulated >= target_minutes:
                    completed = True
                    reason = TerminateReason.COMPLETED.value

        return {
            "task_id": task_id,
            "kind": kind,
            "completed": completed,
            "progress_pct": round(progress, 1),
            "reason": reason,
            "record_data": record_data,
        }


_terminate_evaluator_instance = None


def get_terminate_evaluator() -> TerminateEvaluator:
    global _terminate_evaluator_instance
    if _terminate_evaluator_instance is None:
        _terminate_evaluator_instance = TerminateEvaluator()
    return _terminate_evaluator_instance
