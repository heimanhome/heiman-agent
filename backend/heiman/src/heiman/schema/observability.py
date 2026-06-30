from enum import Enum
from pydantic import BaseModel
from typing import Any


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class MetricPoint(BaseModel):
    name: str
    type: MetricType
    value: float
    labels: dict[str, str] = {}
    timestamp: str


class SystemMetrics(BaseModel):
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    uptime_seconds: float


class SensorStats(BaseModel):
    total_sensors: int
    online_sensors: int
    offline_sensors: int
    data_points_today: int
    data_points_total: int
    by_type: dict[str, int] = {}


class RuleStats(BaseModel):
    total_rules: int
    enabled_rules: int
    triggered_today: int
    triggered_total: int
    actions_executed_today: int


class EventStats(BaseModel):
    total_events: int
    events_today: int
    by_level: dict[str, int] = {}
    by_type: dict[str, int] = {}
    unacknowledged: int


class DatabaseStats(BaseModel):
    db_size_mb: float
    table_count: int
    sensor_logs_count: int
    events_count: int
    rules_count: int


class ObservabilityOverview(BaseModel):
    system: SystemMetrics
    sensor: SensorStats
    rule: RuleStats
    event: EventStats
    database: DatabaseStats
