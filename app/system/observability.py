from __future__ import annotations

from collections import deque
from typing import Deque

from app.system.models import SystemEvent, utc_now


class ObservabilityEventQueue:
    def __init__(self, max_events: int = 1000) -> None:
        self.events: Deque[SystemEvent] = deque(maxlen=max_events)

    def publish(
        self,
        severity: str,
        category: str,
        source: str,
        message: str,
        metadata: dict | None = None,
    ) -> SystemEvent:
        event = SystemEvent(
            utc_now(), severity, category, source, message, metadata or {}
        )
        self.events.append(event)
        return event

    def list(self, limit: int = 100) -> list[SystemEvent]:
        return list(self.events)[-limit:]
