from __future__ import annotations

from app.system.circuit_breaker import CircuitBreakerManager
from app.system.health import HealthManager
from app.system.observability import ObservabilityEventQueue
from app.system.recovery import RecoveryManager
from app.system.snapshot import SnapshotManager
from app.system.watchdog import WatchdogManager


class SystemService:
    def __init__(self) -> None:
        self.health = HealthManager()
        self.watchdog = WatchdogManager()
        self.circuit_breakers = CircuitBreakerManager()
        self.recovery = RecoveryManager()
        self.snapshots = SnapshotManager()
        self.events = ObservabilityEventQueue()

    def status(self) -> dict:
        return {
            "health": self.health.status(),
            "watchdog": self.watchdog.inspect(),
            "circuit_breakers": self.circuit_breakers.status(),
            "recovery": self.recovery.status(),
        }
