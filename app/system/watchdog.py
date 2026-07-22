from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic


@dataclass
class WatchdogManager:
    heartbeat_timeout_seconds: float = 60.0
    reconnect_threshold: int = 5
    error_threshold: int = 5
    heartbeats: dict[str, float] = field(default_factory=dict)
    reconnects: dict[str, int] = field(default_factory=dict)
    errors: dict[str, int] = field(default_factory=dict)

    def heartbeat(self, component: str) -> None:
        self.heartbeats[component] = monotonic()

    def record_reconnect(self, component: str) -> None:
        self.reconnects[component] = self.reconnects.get(component, 0) + 1

    def record_error(self, component: str) -> None:
        self.errors[component] = self.errors.get(component, 0) + 1

    def inspect(self) -> dict[str, list[str]]:
        now = monotonic()
        frozen = [
            name
            for name, ts in self.heartbeats.items()
            if now - ts > self.heartbeat_timeout_seconds
        ]
        reconnecting = [
            name
            for name, count in self.reconnects.items()
            if count >= self.reconnect_threshold
        ]
        loops = [
            name for name, count in self.errors.items() if count >= self.error_threshold
        ]
        return {
            "frozen": frozen,
            "reconnections_excessive": reconnecting,
            "error_loops": loops,
        }
