from __future__ import annotations

import os
import time
from typing import Any

from app.system.models import ComponentHealth, SystemMetrics

COMPONENTS = [
    "Market Data",
    "AI Engine",
    "Analytics",
    "Broker",
    "Portfolio",
    "Database",
    "Memory",
    "CPU",
    "Event Queue",
]


class HealthManager:
    def __init__(self, *, started_at: float | None = None) -> None:
        self.started_at = started_at or time.monotonic()
        self.restart_count = 0

    def check(self, sources: dict[str, Any] | None = None) -> list[ComponentHealth]:
        sources = sources or {}
        rows = []
        for component in COMPONENTS:
            value = sources.get(component)
            if value is False:
                rows.append(
                    ComponentHealth(component, "CRITICAL", "Componente reportó fallo.")
                )
            elif value == "offline":
                rows.append(
                    ComponentHealth(component, "OFFLINE", "Componente offline.")
                )
            elif component == "Memory":
                rows.append(self._memory_check())
            elif component == "CPU":
                rows.append(ComponentHealth(component, "HEALTHY", "CPU disponible."))
            else:
                rows.append(
                    ComponentHealth(component, "HEALTHY", "Componente operativo.")
                )
        return rows

    def status(self, sources: dict[str, Any] | None = None) -> dict[str, Any]:
        components = self.check(sources)
        priority = {"HEALTHY": 0, "WARNING": 1, "CRITICAL": 2, "OFFLINE": 3}
        state = max(components, key=lambda item: priority[item.state]).state
        return {
            "state": state,
            "components": [item.to_public_dict() for item in components],
        }

    def metrics(self, **overrides: Any) -> SystemMetrics:
        data = {"uptime_seconds": time.monotonic() - self.started_at, **overrides}
        return SystemMetrics(**data)

    def _memory_check(self) -> ComponentHealth:
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            total_mb = pages * page_size / 1024 / 1024
        except (ValueError, OSError, AttributeError):
            total_mb = 0
        state = "WARNING" if total_mb and total_mb < 256 else "HEALTHY"
        return ComponentHealth(
            "Memory",
            state,
            "Memoria monitoreada.",
            metadata={"total_mb": round(total_mb, 2)},
        )
