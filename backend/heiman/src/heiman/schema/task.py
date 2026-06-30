import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

_TASK_ID_RE = re.compile(r"^[a-z0-9_]{1,32}$")


class LinkKind(str, Enum):
    RULE = "rule"
    CRON = "cron"


class RecordKind(str, Enum):
    PROGRESS = "progress"
    DURATION = "duration"
    EVENT = "event"


class RecordStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"


class TerminateReason(str, Enum):
    COMPLETED = "completed"
    EXPIRED = "expired"
    ABANDONED = "abandoned"


class ProgressWindow(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    LONGTERM = "longterm"


class TaskCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    task_id: str = Field(..., description="snake_case，[a-z0-9_]{1,32}")
    description: str = Field(..., max_length=200, description="≤200 字符")

    @field_validator("task_id")
    @classmethod
    def _validate_task_id(cls, v: str) -> str:
        if not _TASK_ID_RE.match(v):
            raise ValueError(
                f"task_id 必须匹配 [a-z0-9_]{{1,32}}，收到: {v!r}"
            )
        return v


class TaskUpdateRequest(BaseModel):
    description: str = Field(..., max_length=200)


class TaskLinkAddRequest(BaseModel):
    kind: Literal["rule", "cron"]
    ref: str = Field(..., min_length=1)


class TaskLinkEntry(BaseModel):
    kind: Literal["rule", "cron"]
    ref: str


class TaskFullView(BaseModel):
    task_id: str
    description: str
    status: Literal["active", "paused"]
    paused_at: str | None = None
    created_at: str
    links: list[TaskLinkEntry] = Field(default_factory=list)


class ProgressRecord(BaseModel):
    id: int
    task_id: str
    target: int
    current: int
    unit: str
    window: ProgressWindow
    status: RecordStatus
    created_at: str
    updated_at: str


class DurationRecord(BaseModel):
    id: int
    task_id: str
    target_minutes: int | None = None
    active_session_start_at: str | None = None
    status: RecordStatus
    created_at: str
    updated_at: str


class DurationSession(BaseModel):
    id: int
    task_id: str
    start_at: str
    end_at: str
    duration_seconds: int


class EventRecord(BaseModel):
    id: int
    task_id: str
    status: RecordStatus
    created_at: str
    updated_at: str


class EventEntry(BaseModel):
    id: int
    task_id: str
    description: str
    at: str


class DerivedProgress(BaseModel):
    kind: Literal["progress"] = "progress"
    remaining: int
    progress_pct: float


class DerivedDuration(BaseModel):
    kind: Literal["duration"] = "duration"
    accumulated_minutes_today: int
    remaining_minutes: int | None = None
    active_session_start_at: str | None = None


class DerivedEvent(BaseModel):
    kind: Literal["event"] = "event"
    count_total: int
    count_today: int
    last_at: str | None = None


class ProgressIncrementResult(BaseModel):
    ok: bool = True
    current: int | None = None
    target: int | None = None
    status: RecordStatus | None = None
    derived: DerivedProgress | None = None


class EventAppendResult(BaseModel):
    ok: bool = True
    entry_id: int | None = None
    derived: DerivedEvent | None = None


class SessionStartResult(BaseModel):
    ok: bool = True
    already_active: bool = False
    start_at: str | None = None
    status: RecordStatus | None = None
    derived: DerivedDuration | None = None


class SessionEndResult(BaseModel):
    ok: bool = True
    this_session_minutes: int | None = None
    status: RecordStatus | None = None
    derived: DerivedDuration | None = None


class ProgressInitContent(BaseModel):
    model_config = {"extra": "forbid"}

    target: int = Field(..., gt=0)
    unit: str = Field(..., min_length=1)
    window: ProgressWindow


class DurationInitContent(BaseModel):
    model_config = {"extra": "forbid"}

    target_minutes: int | None = Field(None, gt=0)


class EventInitContent(BaseModel):
    model_config = {"extra": "forbid"}
    pass


class RecordInitRequest(BaseModel):
    model_config = {"extra": "forbid"}

    kind: RecordKind
    content: dict[str, Any] = Field(default_factory=dict)


class ProgressIncrementRequest(BaseModel):
    model_config = {"extra": "forbid"}

    delta: int = 1


class EventAppendRequest(BaseModel):
    model_config = {"extra": "forbid"}

    description: str = Field(..., min_length=1)


class TaskSummaryView(TaskFullView):
    record_kind: RecordKind | None = None
    record: dict | None = None
