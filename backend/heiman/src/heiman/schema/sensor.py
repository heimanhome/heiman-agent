from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class SensorType(str, Enum):
    SMOKE = "smoke"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    CO = "co"
    WATER = "water"
    CONTACT = "contact"
    MOTION = "motion"
    PLUG = "plug"
    SIREN = "siren"
    BUTTON = "button"
    GATEWAY = "gateway"
    REMOTE = "remote"


class SensorStatus(str, Enum):
    NORMAL = "normal"
    ALARM = "alarm"
    WARNING = "warning"
    OFFLINE = "offline"


class SensorData(BaseModel):
    did: str
    name: str
    sensor_type: SensorType
    value: float | int | None = None
    unit: str
    status: SensorStatus
    room_id: str | None = None
    room_name: str | None = None
    home_id: str | None = None
    icon: str | None = None
    battery: int | None = None
    timestamp: datetime = Field(default_factory=datetime.now)


class SensorEventLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SensorEventType(str, Enum):
    SMOKE_ALARM = "smoke_alarm"
    SMOKE_WARNING = "smoke_warning"
    TEMPERATURE_HIGH = "temperature_high"
    TEMPERATURE_LOW = "temperature_low"
    HUMIDITY_HIGH = "humidity_high"
    HUMIDITY_LOW = "humidity_low"
    CO_ALARM = "co_alarm"
    CO_WARNING = "co_warning"
    WATER_LEAK = "water_leak"
    WATER_ALARM = "water_alarm"
    WATER_WARNING = "water_warning"
    DEVICE_OFFLINE = "device_offline"
    DEVICE_ONLINE = "device_online"
    STATUS_REPORT = "status_report"
    TEMP_ALARM = "temp_alarm"
    TEMP_WARNING = "temp_warning"
    HUMIDITY_ALARM = "humidity_alarm"
    HUMIDITY_WARNING = "humidity_warning"
    ALARM = "alarm"
    WARNING = "warning"
    CONTACT_ALARM = "contact_alarm"
    CONTACT_WARNING = "contact_warning"
    MOTION_DETECTED = "motion_detected"
    MOTION_ALARM = "motion_alarm"
    MOTION_WARNING = "motion_warning"
    SIREN_ALARM = "siren_alarm"
    BUTTON_ALARM = "button_alarm"
    PLUG_ALARM = "plug_alarm"
    REMOTE_ALARM = "remote_alarm"
    LOW_BATTERY = "low_battery"
    TAMPER_ALARM = "tamper_alarm"


class SensorEvent(BaseModel):
    event_id: str
    event_type: SensorEventType
    level: SensorEventLevel
    did: str
    device_name: str
    room_name: str | None = None
    home_id: str | None = None
    product_id: str | None = None
    child_device_id: str | None = None
    description: str
    raw_data: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    acknowledged: bool = False