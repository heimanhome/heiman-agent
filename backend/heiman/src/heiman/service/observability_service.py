import logging
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any

from heiman.database.connector import get_db_connector
from heiman.database.sensor_repo import SensorLogRepo
from heiman.database.event_repo import EventRepo
from heiman.database.rule_repo import RuleRepo
from heiman.schema.observability import (
    SystemMetrics,
    SensorStats,
    RuleStats,
    EventStats,
    DatabaseStats,
    ObservabilityOverview,
)

logger = logging.getLogger(__name__)

MAX_LATENCY_SAMPLES = 1000


class ObservabilityService:
    _instance: "ObservabilityService | None" = None
    _init_lock = threading.Lock()

    def __init__(self):
        self.db = get_db_connector()
        self.sensor_repo = SensorLogRepo()
        self.event_repo = EventRepo()
        self.rule_repo = RuleRepo()
        self._start_time = time.time()
        self._latency_samples: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=MAX_LATENCY_SAMPLES)
        )
        self._request_counts: dict[str, int] = defaultdict(int)
        self._error_counts: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ObservabilityService":
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def record_request(self, endpoint: str, latency_ms: float, error: bool = False) -> None:
        with self._lock:
            self._latency_samples[endpoint].append(latency_ms)
            self._request_counts[endpoint] += 1
            if error:
                self._error_counts[endpoint] += 1

    def get_performance_metrics(self) -> dict[str, Any]:
        with self._lock:
            endpoints = set(list(self._latency_samples.keys()) + list(self._request_counts.keys()))
            result = {}
            for ep in endpoints:
                samples = list(self._latency_samples.get(ep, []))
                total_requests = self._request_counts.get(ep, 0)
                total_errors = self._error_counts.get(ep, 0)
                if samples:
                    avg_latency = sum(samples) / len(samples)
                    max_latency = max(samples)
                    min_latency = min(samples)
                    sorted_samples = sorted(samples)
                    p50_idx = int(len(sorted_samples) * 0.5)
                    p95_idx = int(len(sorted_samples) * 0.95)
                    p99_idx = int(len(sorted_samples) * 0.99)
                    p50 = sorted_samples[min(p50_idx, len(sorted_samples) - 1)]
                    p95 = sorted_samples[min(p95_idx, len(sorted_samples) - 1)]
                    p99 = sorted_samples[min(p99_idx, len(sorted_samples) - 1)]
                else:
                    avg_latency = 0
                    max_latency = 0
                    min_latency = 0
                    p50 = 0
                    p95 = 0
                    p99 = 0
                result[ep] = {
                    "total_requests": total_requests,
                    "total_errors": total_errors,
                    "error_rate": (total_errors / total_requests * 100) if total_requests > 0 else 0,
                    "avg_latency_ms": round(avg_latency, 2),
                    "max_latency_ms": round(max_latency, 2),
                    "min_latency_ms": round(min_latency, 2),
                    "p50_ms": round(p50, 2),
                    "p95_ms": round(p95, 2),
                    "p99_ms": round(p99, 2),
                    "samples": len(samples),
                }
            return {
                "endpoints": result,
                "total_requests": sum(self._request_counts.values()),
                "total_errors": sum(self._error_counts.values()),
                "uptime_seconds": round(time.time() - self._start_time, 1),
            }

    def get_system_metrics(self) -> SystemMetrics:
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            return SystemMetrics(
                cpu_percent=round(cpu_percent, 1),
                memory_percent=round(mem.percent, 1),
                memory_used_mb=round(mem.used / (1024 * 1024), 1),
                memory_total_mb=round(mem.total / (1024 * 1024), 1),
                disk_percent=round(disk.percent, 1),
                disk_used_gb=round(disk.used / (1024 * 1024 * 1024), 1),
                disk_total_gb=round(disk.total / (1024 * 1024 * 1024), 1),
                uptime_seconds=round(time.time() - self._start_time, 1),
            )
        except ImportError:
            logger.warning("psutil not available, returning basic metrics")
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                memory_total_mb=0.0,
                disk_percent=0.0,
                disk_used_gb=0.0,
                disk_total_gb=0.0,
                uptime_seconds=round(time.time() - self._start_time, 1),
            )

    def get_sensor_stats(self) -> SensorStats:
        try:
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                total_sensors_row = cursor.execute(
                    "SELECT COUNT(DISTINCT did) as cnt FROM sensor_logs"
                ).fetchone()
                total_sensors = total_sensors_row["cnt"] if total_sensors_row else 0

                today_row = cursor.execute(
                    "SELECT COUNT(*) as cnt FROM sensor_logs WHERE timestamp >= ?",
                    (today_start,),
                ).fetchone()
                data_points_today = today_row["cnt"] if today_row else 0

                total_row = cursor.execute(
                    "SELECT COUNT(*) as cnt FROM sensor_logs"
                ).fetchone()
                data_points_total = total_row["cnt"] if total_row else 0

                by_type_rows = cursor.execute(
                    "SELECT sensor_type, COUNT(*) as cnt FROM sensor_logs GROUP BY sensor_type"
                ).fetchall()
                by_type = {row["sensor_type"]: row["cnt"] for row in by_type_rows}

                offline_threshold = (datetime.now() - timedelta(minutes=60)).isoformat()
                online_row = cursor.execute(
                    "SELECT COUNT(DISTINCT did) as cnt FROM sensor_logs WHERE timestamp >= ?",
                    (offline_threshold,),
                ).fetchone()
                online_sensors = online_row["cnt"] if online_row else 0
                offline_sensors = total_sensors - online_sensors

                return SensorStats(
                    total_sensors=total_sensors,
                    online_sensors=online_sensors,
                    offline_sensors=offline_sensors,
                    data_points_today=data_points_today,
                    data_points_total=data_points_total,
                    by_type=by_type,
                )
        except Exception as e:
            logger.error("Failed to get sensor stats: %s", e)
            return SensorStats(
                total_sensors=0,
                online_sensors=0,
                offline_sensors=0,
                data_points_today=0,
                data_points_total=0,
                by_type={},
            )

    def get_rule_stats(self) -> RuleStats:
        try:
            rules = self.rule_repo.get_all()
            enabled_rules = sum(1 for r in rules if r.enabled)

            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                total_row = cursor.execute(
                    "SELECT COUNT(*) as cnt FROM rule_executions"
                ).fetchone()
                triggered_total = total_row["cnt"] if total_row else 0

                today_row = cursor.execute(
                    "SELECT COUNT(*) as cnt FROM rule_executions WHERE executed_at >= ?",
                    (today_start,),
                ).fetchone()
                triggered_today = today_row["cnt"] if today_row else 0

                actions_today_row = cursor.execute(
                    "SELECT COUNT(*) as cnt FROM rule_executions WHERE executed_at >= ?",
                    (today_start,),
                ).fetchone()
                actions_executed_today = actions_today_row["cnt"] if actions_today_row else 0

            return RuleStats(
                total_rules=len(rules),
                enabled_rules=enabled_rules,
                triggered_today=triggered_today,
                triggered_total=triggered_total,
                actions_executed_today=actions_executed_today,
            )
        except Exception as e:
            logger.error("Failed to get rule stats: %s", e)
            return RuleStats(
                total_rules=0,
                enabled_rules=0,
                triggered_today=0,
                triggered_total=0,
                actions_executed_today=0,
            )

    def get_event_stats(self) -> EventStats:
        try:
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                total_row = cursor.execute(
                    "SELECT COUNT(*) as cnt FROM events"
                ).fetchone()
                total_events = total_row["cnt"] if total_row else 0

                today_row = cursor.execute(
                    "SELECT COUNT(*) as cnt FROM events WHERE timestamp >= ?",
                    (today_start,),
                ).fetchone()
                events_today = today_row["cnt"] if today_row else 0

                by_level_rows = cursor.execute(
                    "SELECT level, COUNT(*) as cnt FROM events GROUP BY level"
                ).fetchall()
                by_level = {row["level"]: row["cnt"] for row in by_level_rows}

                by_type_rows = cursor.execute(
                    "SELECT event_type, COUNT(*) as cnt FROM events GROUP BY event_type"
                ).fetchall()
                by_type = {row["event_type"]: row["cnt"] for row in by_type_rows}

                unack_row = cursor.execute(
                    "SELECT COUNT(*) as cnt FROM events WHERE acknowledged = 0"
                ).fetchone()
                unacknowledged = unack_row["cnt"] if unack_row else 0

                return EventStats(
                    total_events=total_events,
                    events_today=events_today,
                    by_level=by_level,
                    by_type=by_type,
                    unacknowledged=unacknowledged,
                )
        except Exception as e:
            logger.error("Failed to get event stats: %s", e)
            return EventStats(
                total_events=0,
                events_today=0,
                by_level={},
                by_type={},
                unacknowledged=0,
            )

    def get_database_stats(self) -> DatabaseStats:
        try:
            db_info = self.db.get_database_info()
            db_size_mb = round(db_info.get("size", 0) / (1024 * 1024), 2)
            table_count = len(db_info.get("tables", []))

            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                sensor_row = cursor.execute(
                    "SELECT COUNT(*) as cnt FROM sensor_logs"
                ).fetchone()
                sensor_logs_count = sensor_row["cnt"] if sensor_row else 0

                events_row = cursor.execute(
                    "SELECT COUNT(*) as cnt FROM events"
                ).fetchone()
                events_count = events_row["cnt"] if events_row else 0

                rules_row = cursor.execute(
                    "SELECT COUNT(*) as cnt FROM rules"
                ).fetchone()
                rules_count = rules_row["cnt"] if rules_row else 0

                return DatabaseStats(
                    db_size_mb=db_size_mb,
                    table_count=table_count,
                    sensor_logs_count=sensor_logs_count,
                    events_count=events_count,
                    rules_count=rules_count,
                )
        except Exception as e:
            logger.error("Failed to get database stats: %s", e)
            return DatabaseStats(
                db_size_mb=0.0,
                table_count=0,
                sensor_logs_count=0,
                events_count=0,
                rules_count=0,
            )

    def get_overview(self) -> ObservabilityOverview:
        return ObservabilityOverview(
            system=self.get_system_metrics(),
            sensor=self.get_sensor_stats(),
            rule=self.get_rule_stats(),
            event=self.get_event_stats(),
            database=self.get_database_stats(),
        )
