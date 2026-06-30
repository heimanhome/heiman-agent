"""SQLite 连接与四表 + view 初始化。

Schema 版本通过 PRAGMA user_version 管理。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

_TRACES_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
  trace_id              TEXT    NOT NULL PRIMARY KEY,
  timestamp             INTEGER NOT NULL,
  device_count          INTEGER,
  skipped               INTEGER DEFAULT 0,
  in_delay_ms           REAL,
  out_delay_ms          REAL,
  decode_ms             REAL,
  collect_ms            REAL,
  convert_ms            REAL,
  log_ms                REAL,
  cycle_total_ms        REAL,
  pipeline_total_ms     REAL,
  window_duration_ms    REAL,
  window_first_frame_recv_ms INTEGER,
  stream_lag_ms         REAL,
  gate_ms               REAL,
  gate_video_ms         REAL,
  gate_audio_ms         REAL,
  gate_video_pass       INTEGER,
  gate_audio_pass       INTEGER,
  gate_hold_pass        INTEGER,
  identity_ms           REAL,
  omni_ms               REAL,
  omni_call_count       INTEGER,
  omni_error_count      INTEGER DEFAULT 0,
  timing_detail         TEXT,
  dropped_windows_total INTEGER DEFAULT 0,
  overflow_count_total  INTEGER DEFAULT 0,
  cycle_error_msg       TEXT
);
CREATE INDEX IF NOT EXISTS idx_traces_ts ON traces(timestamp);
"""

_TRACES_DEVICE_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces_device (
  device_trace_id   TEXT    NOT NULL PRIMARY KEY,
  cycle_id          TEXT    NOT NULL,
  timestamp         INTEGER NOT NULL,
  device_id         TEXT    NOT NULL,
  room_name         TEXT,
  decode_video_avg_ms   REAL,
  decode_audio_avg_ms   REAL,
  video_frame_count     INTEGER,
  audio_frame_count     INTEGER,
  gate_ms           REAL,
  gate_video_ms     REAL,
  gate_audio_ms     REAL,
  gate_video_pass   INTEGER,
  gate_audio_pass   INTEGER,
  gate_hold_pass    INTEGER,
  gate_skipped      INTEGER DEFAULT 0,
  gate_video_score  REAL,
  gate_audio_energy REAL,
  identity_ms       REAL,
  omni_ms                REAL,
  omni_error_code        TEXT,
  omni_retry_count       INTEGER DEFAULT 0,
  dropped_windows_count  INTEGER DEFAULT 0,
  overflow_count         INTEGER DEFAULT 0,
  max_buffer_depth       INTEGER DEFAULT 0,
  last_overflow_action   TEXT
);
CREATE INDEX IF NOT EXISTS idx_td_cycle ON traces_device(cycle_id);
CREATE INDEX IF NOT EXISTS idx_td_device_ts ON traces_device(device_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_td_room_ts ON traces_device(room_name, timestamp);
CREATE INDEX IF NOT EXISTS idx_td_ts ON traces_device(timestamp);
"""

_EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  event_id    TEXT    NOT NULL PRIMARY KEY,
  timestamp   INTEGER NOT NULL,
  event_type  TEXT    NOT NULL,
  trace_id    TEXT,
  source      TEXT,
  payload     TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_trace ON events(trace_id);
CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events(event_type, timestamp);
"""

_AGENT_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_runs (
  run_id            TEXT    NOT NULL PRIMARY KEY,
  trace_id          TEXT    NOT NULL,
  timestamp         INTEGER NOT NULL,
  source            TEXT    NOT NULL,
  query             TEXT,
  webhook_rtt_ms    REAL,
  duration_ms       REAL,
  llm_call_count    INTEGER,
  tool_call_count   INTEGER,
  llm_total_ms      REAL,
  tool_total_ms     REAL,
  tool_max_ms       REAL,
  slowest_tool_name TEXT,
  success           INTEGER,
  error_count       INTEGER,
  error_msg         TEXT,
  jsonl_path        TEXT
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_trace ON agent_runs(trace_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_ts ON agent_runs(timestamp);
CREATE INDEX IF NOT EXISTS idx_agent_runs_source_ts ON agent_runs(source, timestamp);
CREATE INDEX IF NOT EXISTS idx_agent_runs_success ON agent_runs(success) WHERE success IS NOT NULL;
"""

_TRACES_V_VIEW = """
CREATE VIEW IF NOT EXISTS traces_v AS
SELECT
  t.*,
  CASE WHEN EXISTS(SELECT 1 FROM agent_runs WHERE trace_id = t.trace_id) THEN 1 ELSE 0 END AS has_agent_turn,
  CASE WHEN window_duration_ms > 0 THEN cycle_total_ms / window_duration_ms ELSE NULL END AS rtf,
  CASE WHEN window_duration_ms > 0 THEN pipeline_total_ms / window_duration_ms ELSE NULL END AS rtf_pipeline,
  CASE WHEN window_duration_ms > 0
       THEN (cycle_total_ms + COALESCE(in_delay_ms, 0)) / window_duration_ms
       ELSE NULL END AS rtf_e2e,
  CASE WHEN window_duration_ms > 0
       THEN (cycle_total_ms + COALESCE(in_delay_ms, 0) + COALESCE(stream_lag_ms, 0)) / window_duration_ms
       ELSE NULL END AS rtf_stream_e2e,
  CASE WHEN window_duration_ms > 0 AND omni_ms IS NOT NULL
       THEN omni_ms / window_duration_ms ELSE NULL END AS rtf_omni,
  CASE WHEN gate_video_pass = 1 OR gate_audio_pass = 1 OR gate_hold_pass = 1 THEN 1 ELSE 0 END AS gate_passed
FROM traces t;
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    """打开连接,只设 connection-level PRAGMA。"""
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA user_version").fetchone()[0]

    if cur == SCHEMA_VERSION:
        return

    if cur > SCHEMA_VERSION:
        raise RuntimeError(
            f"db schema v{cur} 与代码 v{SCHEMA_VERSION} 不匹配,"
            "db 版本高于代码版本,请用对应版本启动。"
        )

    if cur == 0:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='traces'"
        ).fetchone()
        if row:
            raise RuntimeError(
                "检测到无 schema 版本号的老 observability db,"
                "请删除 db 文件后重启。"
            )
        conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_TRACES_SCHEMA)
        conn.executescript(_TRACES_DEVICE_SCHEMA)
        conn.executescript(_EVENTS_SCHEMA)
        conn.executescript(_AGENT_RUNS_SCHEMA)
        conn.executescript(_TRACES_V_VIEW)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return

    raise RuntimeError(
        f"db schema v{cur} → v{SCHEMA_VERSION} 无 migration 注册,"
        "请删除 db 文件后重启。"
    )