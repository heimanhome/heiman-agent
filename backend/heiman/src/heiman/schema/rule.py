from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from .sensor import SensorType


class RuleActionType(str, Enum):
    ALERT = "alert"
    LOG = "log"
    WEBHOOK = "webhook"
    MESSAGE = "message"
    DEVICE_CONTROL = "device_control"


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


class SuggestionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RuleSuggestion(BaseModel):
    suggestion_id: str
    user_id: str
    home_id: str | None = None
    name: str
    description: str
    confidence: float
    pattern_type: str
    trigger_device_id: str | None = None
    trigger_device_name: str | None = None
    action_device_id: str | None = None
    action_device_name: str | None = None
    rule_data: dict = Field(default_factory=dict)
    status: SuggestionStatus = SuggestionStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    approved_at: datetime | None = None
    rejected_at: datetime | None = None