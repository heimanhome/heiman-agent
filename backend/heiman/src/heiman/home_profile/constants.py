"""home_profile configuration constants."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecayConfig:
    half_life: int
    floor: float
    expirable: bool


PROMOTE = {
    "min_evidence": 3,
    "min_span_days": 2,
    "min_confidence": 1.0,
    "expire_days": 30,
}

DECAY: dict[str, DecayConfig] = {
    "member_health": DecayConfig(365, 0.6, False),
    "member_persona": DecayConfig(365, 0.4, False),
    "family": DecayConfig(365, 0.3, False),
    "space": DecayConfig(365, 0.3, False),
    "device": DecayConfig(365, 0.2, True),
    "member_routine": DecayConfig(180, 0.0, True),
    "member_entertain": DecayConfig(180, 0.0, True),
    "member_preference": DecayConfig(365, 0.2, True),
}

DEFAULT_DECAY = DecayConfig(180, 0.0, True)

SOURCE_BONUS = {"user_told": 2.0, "observed": 1.0}

USER_TOLD_FLOOR = 0.3

LIMITS = {
    "max_evidence_log": 10,
    "max_profile_tokens": 2000,
    "max_candidates": 500,
    "max_profile_entries": 300,
    "max_last_seen_days": 365,
}
