from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Callable, Any


@dataclass
class RecoveryManager:
    actions: dict[str, Callable[[], Any]] = field(default_factory=dict)
    last_recovery_ms: float = 0.0
    history: list[dict[str, Any]] = field(default_factory=list)

    def register(self, component: str, action: Callable[[], Any]) -> None:
        self.actions[component] = action

    def recover(self, component: str) -> dict[str, Any]:
        start = monotonic()
        if component not in self.actions:
            result = {
                "component": component,
                "recovered": False,
                "reason": "Sin acción de recuperación.",
            }
        else:
            self.actions[component]()
            result = {
                "component": component,
                "recovered": True,
                "reason": "Recuperación ejecutada sin órdenes.",
            }
        self.last_recovery_ms = (monotonic() - start) * 1000
        result["recovery_time_ms"] = self.last_recovery_ms
        self.history.append(result)
        return result

    def status(self) -> dict[str, Any]:
        return {
            "registered": sorted(self.actions),
            "last_recovery_ms": self.last_recovery_ms,
            "history": self.history[-20:],
        }
