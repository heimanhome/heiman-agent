"""home_profile schema — entry models + API request bodies."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

EntryType = Literal[
    "member_persona",
    "member_health",
    "member_routine",
    "member_entertain",
    "member_preference",
    "family",
    "space",
    "device",
]
EntrySource = Literal["observed", "user_told"]
Target = Literal["profile", "candidates", "both"]

_RESERVED_SUBJECTS = frozenset({"shared", "general"})


class Entry(BaseModel):
    id: str
    type: EntryType
    subject_id: str | None = None
    subject_name: str | None = None
    content: str
    confidence: float
    evidence_count: int
    first_seen: str
    last_seen: str
    source: EntrySource
    evidence_log: list[str] = Field(default_factory=list)


class ProfileEntry(Entry):
    archived: bool = False


class CandidatesIndex(BaseModel):
    version: int = 1
    entries: list[Entry] = Field(default_factory=list)


class ProfileIndex(BaseModel):
    version: int = 1
    entries: list[ProfileEntry] = Field(default_factory=list)


class EntryPayload(BaseModel):
    type: EntryType
    subject_id: str | None = None
    subject_name: str | None = None
    content: str
    confidence: float = 0.5
    source: EntrySource = "observed"
    evidence_log: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize_reserved_subject(self) -> "EntryPayload":
        if self.subject_name in _RESERVED_SUBJECTS:
            self.subject_id = None
        return self


class EntryEdit(BaseModel):
    type: EntryType | None = None
    subject_id: str | None = None
    subject_name: str | None = None
    content: str | None = None
    confidence: float | None = None
    source: EntrySource | None = None
    evidence_count: int | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    evidence_log: list[str] | None = None


class CandidateOp(BaseModel):
    op: Literal["add", "merge", "update", "delete"]
    id: str | None = None
    date: str
    entry: EntryPayload | None = None
    edit: EntryEdit | None = None
    evidence_log: str | None = None
    confidence_delta: float | None = None


class ProfileOp(BaseModel):
    op: Literal["add", "merge", "replace", "update", "delete"]
    id: str | None = None
    date: str | None = None
    entry: EntryPayload | None = None
    edit: EntryEdit | None = None
    from_: str | None = Field(default=None, alias="from")
    evidence_log: str | None = None
    confidence_delta: float | None = None

    model_config = {"populate_by_name": True}


class CandidateWriteBody(BaseModel):
    ops: list[CandidateOp]


class ProfileWriteBody(BaseModel):
    ops: list[ProfileOp]
    user_edit: bool = False


class ReassignMapping(BaseModel):
    from_subject_ids: list[str] = Field(default_factory=list)
    from_subject_names: list[str] = Field(default_factory=list)
    to_subject_id: str | None = None
    to_subject_name: str | None = None


class ReassignBody(BaseModel):
    mappings: list[ReassignMapping]


class ImportBody(BaseModel):
    profile: list[ProfileEntry] = Field(default_factory=list)
    candidates: list[Entry] = Field(default_factory=list)


class ResetBody(ImportBody):
    commit: bool = True


class OpResult(BaseModel):
    op: str
    id: str
    ok: bool
    message: str | None = None
