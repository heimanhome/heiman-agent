import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


logger = logging.getLogger(__name__)


class PerceptionType(str, Enum):
    MOTION = "motion"
    CONTACT = "contact"
    SOUND = "sound"
    FACE = "face"
    SPEECH = "speech"
    ENVIRONMENT = "environment"
    ACTIVITY = "activity"


@dataclass
class PerceptionEvent:
    event_id: str
    type: PerceptionType
    source: str
    location: Optional[str] = None
    confidence: float = 0.0
    timestamp: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerceptionWindow:
    window_id: str
    start_time: float
    end_time: float
    events: List[PerceptionEvent] = field(default_factory=list)


class PerceptionEngine:
    def __init__(self):
        self._collectors: Dict[str, Any] = {}
        self._processors: Dict[str, Any] = {}
        self._event_buffer: List[PerceptionEvent] = []
        self._running = False
        self._window_duration = 5.0
        self._last_window_time = 0.0

    async def start(self):
        self._running = True
        logger.info("Perception engine started")

        asyncio.create_task(self._window_loop())

    async def stop(self):
        self._running = False
        logger.info("Perception engine stopped")

    async def _window_loop(self):
        while self._running:
            current_time = asyncio.get_event_loop().time()
            if current_time - self._last_window_time >= self._window_duration:
                await self._process_window()
                self._last_window_time = current_time
            await asyncio.sleep(0.1)

    async def _process_window(self):
        if not self._event_buffer:
            return

        window = PerceptionWindow(
            window_id=f"win-{int(asyncio.get_event_loop().time())}",
            start_time=self._last_window_time,
            end_time=asyncio.get_event_loop().time(),
            events=self._event_buffer.copy(),
        )

        self._event_buffer.clear()

        await self._dispatch_to_processors(window)

    async def _dispatch_to_processors(self, window: PerceptionWindow):
        for name, processor in self._processors.items():
            try:
                await processor.process(window)
            except Exception as e:
                logger.error(f"Processor {name} failed: {e}")

    def register_collector(self, name: str, collector):
        self._collectors[name] = collector
        logger.info(f"Registered collector: {name}")

    def register_processor(self, name: str, processor):
        self._processors[name] = processor
        logger.info(f"Registered processor: {name}")

    async def submit_event(self, event: PerceptionEvent):
        self._event_buffer.append(event)
        logger.debug(f"Submitted event: {event.type} from {event.source}")

    async def get_recent_events(self, limit: int = 20) -> List[PerceptionEvent]:
        return self._event_buffer[-limit:]

    async def get_current_context(self) -> Dict[str, Any]:
        context = {}
        
        motion_events = [e for e in self._event_buffer if e.type == PerceptionType.MOTION]
        context["motion_detected"] = len(motion_events) > 0
        
        contact_events = [e for e in self._event_buffer if e.type == PerceptionType.CONTACT]
        context["contact_changed"] = len(contact_events) > 0
        
        face_events = [e for e in self._event_buffer if e.type == PerceptionType.FACE]
        context["face_detected"] = len(face_events) > 0
        
        speech_events = [e for e in self._event_buffer if e.type == PerceptionType.SPEECH]
        context["speech_detected"] = len(speech_events) > 0
        
        return context