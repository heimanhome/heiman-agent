"""可观测性统计视图。"""
from __future__ import annotations

import sqlite3
from typing import Any

VIEWS: dict[str, Any] = {}


def _bucket_sql(bucket: str) -> str:
    """时间桶 SQL 表达式。"""
    mapping = {
        "1m": "strftime('%Y-%m-%d %H:%M', timestamp / 1000, 'unixepoch')",
        "5m": "strftime('%Y-%m-%d %H:%M', (timestamp / 1000 / 300) * 300, 'unixepoch')",
        "15m": "strftime('%Y-%m-%d %H:%M', (timestamp / 1000 / 900) * 900, 'unixepoch')",
        "1h": "strftime('%Y-%m-%d %H:00', timestamp / 1000, 'unixepoch')",
        "6h": "strftime('%Y-%m-%d %H:00', (timestamp / 1000 / 21600) * 21600, 'unixepoch')",
        "1d": "strftime('%Y-%m-%d', timestamp / 1000, 'unixepoch')",
    }
    return mapping.get(bucket, mapping["1h"])


def _build_time_clause(since: int | None, until: int | None) -> tuple[str, list[Any]]:
    """构建 WHERE 时间条件。"""
    clauses: list[str] = []
    params: list[Any] = []
    if since is not None:
        clauses.append("timestamp >= ?")
        params.append(since)
    if until is not None:
        clauses.append("timestamp <= ?")
        params.append(until)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _view_trace_count(conn: sqlite3.Connection, bucket: str, since: int | None, until: int | None):
    """trace 数量统计。"""
    where, params = _build_time_clause(since, until)
    bucket_expr = _bucket_sql(bucket)
    sql = f"""
        SELECT {bucket_expr} as bucket, COUNT(*) as count
        FROM traces {where}
        GROUP BY bucket ORDER BY bucket
    """
    rows = conn.execute(sql, params).fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM traces LIMIT 0").description]
    return [dict(zip(["bucket", "count"], r)) for r in rows]


def _view_agent_run_count(conn: sqlite3.Connection, bucket: str, since: int | None, until: int | None):
    """agent_run 数量统计。"""
    where, params = _build_time_clause(since, until)
    bucket_expr = _bucket_sql(bucket)
    sql = f"""
        SELECT {bucket_expr} as bucket, COUNT(*) as count, SUM(success) as success
        FROM agent_runs {where}
        GROUP BY bucket ORDER BY bucket
    """
    rows = conn.execute(sql, params).fetchall()
    return [{"bucket": r[0], "count": r[1], "success": r[2]} for r in rows]


def _view_event_count(conn: sqlite3.Connection, bucket: str, since: int | None, until: int | None):
    """event 数量统计。"""
    where, params = _build_time_clause(since, until)
    bucket_expr = _bucket_sql(bucket)
    sql = f"""
        SELECT {bucket_expr} as bucket, event_type, COUNT(*) as count
        FROM events {where}
        GROUP BY bucket, event_type ORDER BY bucket, event_type
    """
    rows = conn.execute(sql, params).fetchall()
    return [{"bucket": r[0], "event_type": r[1], "count": r[2]} for r in rows]


VIEWS["trace_count"] = _view_trace_count
VIEWS["agent_run_count"] = _view_agent_run_count
VIEWS["event_count"] = _view_event_count