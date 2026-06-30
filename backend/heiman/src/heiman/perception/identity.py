import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


logger = logging.getLogger(__name__)


class IdentityStatus(str, Enum):
    PRESENT = "present"
    AWAY = "away"
    UNKNOWN = "unknown"


class PersonRole(str, Enum):
    OWNER = "owner"
    FAMILY = "family"
    GUEST = "guest"
    STRANGER = "stranger"


@dataclass
class PersonRecord:
    person_id: str
    name: str
    role: PersonRole = PersonRole.FAMILY
    avatar: Optional[str] = None
    status: IdentityStatus = IdentityStatus.UNKNOWN
    last_seen: Optional[float] = None
    confidence: float = 0.0


@dataclass
class IdentityAssignment:
    track_id: str
    person_id: Optional[str] = None
    name: Optional[str] = None
    confidence: float = 0.0


class IdentityEngine:
    def __init__(self):
        self._library: Dict[str, PersonRecord] = {}
        self._tracks: Dict[str, Any] = {}
        self._current_persons: Dict[str, PersonRecord] = {}
        self._history: List[Dict] = []

    def add_person(self, person_id: str, name: str, role: str = "family", avatar: Optional[str] = None):
        person = PersonRecord(
            person_id=person_id,
            name=name,
            role=PersonRole(role.lower()),
            avatar=avatar,
        )
        self._library[person_id] = person
        logger.info(f"Added person: {name} ({person_id})")
        return person

    def remove_person(self, person_id: str):
        if person_id in self._library:
            del self._library[person_id]
            logger.info(f"Removed person: {person_id}")

    def list_persons(self) -> List[PersonRecord]:
        return list(self._library.values())

    def get_person(self, person_id: str) -> Optional[PersonRecord]:
        return self._library.get(person_id)

    async def identify(self, features: Dict[str, Any]) -> IdentityAssignment:
        max_confidence = 0.0
        best_match = None

        for person_id, person in self._library.items():
            confidence = self._calculate_similarity(features, person)
            if confidence > max_confidence and confidence > 0.5:
                max_confidence = confidence
                best_match = person_id

        if best_match:
            person = self._library[best_match]
            person.status = IdentityStatus.PRESENT
            person.last_seen = asyncio.get_event_loop().time()
            person.confidence = max_confidence
            self._current_persons[best_match] = person

            return IdentityAssignment(
                track_id=f"track-{int(asyncio.get_event_loop().time())}",
                person_id=best_match,
                name=person.name,
                confidence=max_confidence,
            )

        return IdentityAssignment(
            track_id=f"track-{int(asyncio.get_event_loop().time())}",
            confidence=0.0,
        )

    def _calculate_similarity(self, features: Dict[str, Any], person: PersonRecord) -> float:
        if "face_embedding" in features and person.avatar:
            return 0.7 + (features.get("confidence", 0) * 0.3)
        if "name" in features and features["name"].lower() == person.name.lower():
            return 0.8
        return 0.0

    def get_current_persons(self) -> List[PersonRecord]:
        return list(self._current_persons.values())

    async def update_status(self, person_id: str, status: str):
        if person_id in self._library:
            self._library[person_id].status = IdentityStatus(status.lower())
            self._library[person_id].last_seen = asyncio.get_event_loop().time()

    async def mark_away(self, timeout: float = 300.0):
        current_time = asyncio.get_event_loop().time()
        for person_id, person in list(self._current_persons.items()):
            if person.last_seen and current_time - person.last_seen > timeout:
                person.status = IdentityStatus.AWAY
                del self._current_persons[person_id]
                logger.info(f"Marked away: {person.name}")

    async def get_recent_activity(self) -> Dict:
        return {
            "current_persons": [
                {
                    "person_id": p.person_id,
                    "name": p.name,
                    "role": p.role.value,
                    "status": p.status.value,
                }
                for p in self.get_current_persons()
            ],
            "activity_history": self._history[-20:],
        }