"""Lightweight metrics recorder for observability DB.

Writes cycle traces, observability events, and agent run records
into the observability SQLite database.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from uuid import uuid4
from typing import Any

from heiman.observability.metrics_db import connect

logger = logging.getLogger(__name__)


class MetricsRecorder:
    """Records observability data to the observability SQLite DB."""

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        return connect(self._db_path)

    def record_cycle(
        self,
        trace_id: str,
        timestamp: int,
        device_count: int,
        cycle_total_ms: float,
        pipeline_total_ms: float | None = None,
        collect_ms: float = 0.0,
        log_ms: float = 0.0,
        error_msg: str | None = None,
    ) -> None:
        """Record a single collection cycle trace."""
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO traces
                   (trace_id, timestamp, device_count, skipped, cycle_total_ms,
                    pipeline_total_ms, collect_ms, log_ms, decode_ms, convert_ms,
                    gate_ms, identity_ms, omni_ms, omni_call_count, omni_error_count,
                    in_delay_ms, out_delay_ms, cycle_error_msg)
                   VALUES (?, ?, ?, 0, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?)""",
                (
                    trace_id, timestamp, device_count,
                    cycle_total_ms,
                    pipeline_total_ms or cycle_total_ms,
                    collect_ms, log_ms,
                    error_msg,
                ),
            )
            conn.close()
        except Exception as e:
            logger.warning("[MetricsRecorder] Failed to record cycle: %s", e)

    def record_event(
        self,
        event_type: str,
        source: str,
        payload: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        """Record an observability event."""
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO events (event_id, timestamp, event_type, trace_id, source, payload)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid4()),
                    int(time.time() * 1000),
                    event_type,
                    trace_id,
                    source,
                    json.dumps(payload or {}, ensure_ascii=False, default=str),
                ),
            )
            conn.close()
        except Exception as e:
            logger.warning("[MetricsRecorder] Failed to record event: %s", e)

    def record_agent_run(
        self,
        run_id: str,
        trace_id: str,
        source: str,
        query: str,
        duration_ms: float,
        success: bool = True,
        error_msg: str | None = None,
    ) -> None:
        """Record an agent run."""
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO agent_runs
                   (run_id, trace_id, timestamp, source, query, duration_ms,
                    llm_call_count, tool_call_count, success, error_count, error_msg)
                   VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?)""",
                (
                    run_id, trace_id,
                    int(time.time() * 1000),
                    source, query, duration_ms,
                    1 if success else 0,
                    0 if success else 1,
                    error_msg,
                ),
            )
            conn.close()
        except Exception as e:
            logger.warning("[MetricsRecorder] Failed to record agent run: %s", e)


_recorder_instance: MetricsRecorder | None = None


def init_recorder(db_path: str) -> MetricsRecorder:
    global _recorder_instance
    _recorder_instance = MetricsRecorder(db_path)
    return _recorder_instance


def get_recorder() -> MetricsRecorder | None:
    return _recorder_instance
