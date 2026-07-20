"""Event bus for real-time event distribution via SSE."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class EventBus:
    """Simple in-memory event bus for SSE broadcasting."""

    def __init__(self):
        self._subscribers: set[asyncio.Queue] = set()
        self._history: list[dict[str, Any]] = []
        self._max_history = 100
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to events and get a queue."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers.add(queue)
            for event in self._history[-20:]:
                await queue.put(event)
        logger.debug("New SSE subscriber connected, total: %d", len(self._subscribers))
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from events."""
        async with self._lock:
            self._subscribers.discard(queue)
        logger.debug("SSE subscriber disconnected, total: %d", len(self._subscribers))

    async def publish(self, event_type: str | dict, data: dict[str, Any] | None = None) -> None:
        """Publish an event to all subscribers.
        
        Supports two calling formats:
        1. publish(event_type: str, data: dict)
        2. publish({"event": "...", "data": {...}})
        """
        if isinstance(event_type, dict):
            event_dict = event_type
            event_type = event_dict.get("event", "message")
            data = event_dict.get("data", {})
        
        event = {
            "id": datetime.now().timestamp(),
            "event": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }

        async with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

            dead_queues: set[asyncio.Queue] = set()
            for queue in self._subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    dead_queues.add(queue)

            for dq in dead_queues:
                self._subscribers.discard(dq)

        logger.debug("Published event: type=%s, subscribers=%d", event_type, len(self._subscribers))

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent event history."""
        return self._history[-limit:]

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


_event_bus_instance = None


def get_event_bus() -> EventBus:
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance
