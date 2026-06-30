from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from .sensor import SensorType


class RuleActionType(str, Enum):
    ALERT = "alert"
    LOG = "log"
    WEBHOOK = "webhook"
    MESSAGE = "message"


class RuleCondition(BaseModel):
    did: str | None = None
    sensor_type: SensorType
    operator: str
    threshold: float | int | list | None = None
    window_seconds: int | None = None


class RuleAction(BaseModel):
    action_id: str | None = None
    action_type: RuleActionType
    payload: dict = Field(default_factory=dict)


class Rule(BaseModel):
    rule_id: str
    name: str
    description: str | None = None
    enabled: bool = True
    conditions: list[RuleCondition] = Field(default_factory=list)
    actions: list[RuleAction] = Field(default_factory=list)
    cooldown_minutes: int = 5
    home_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)