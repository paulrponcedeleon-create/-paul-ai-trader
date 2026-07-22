from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

HealthState = Literal["HEALTHY", "WARNING", "CRITICAL", "OFFLINE"]
CircuitState = Literal["CLOSED", "OPEN", "HALF_OPEN"]
Severity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]
Category = Literal["System", "Broker", "AI", "Paper", "Analytics", "Risk", "Market"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ComponentHealth:
    name: str
    state: HealthState
    message: str
    checked_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state,
            "message": self.message,
            "checked_at": self.checked_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class SystemEvent:
    timestamp: datetime
    severity: Severity
    category: Category
    source: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity,
            "category": self.category,
            "source": self.source,
            "message": self.message,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class SystemMetrics:
    uptime_seconds: float
    restart_count: int = 0
    reconnect_count: int = 0
    broker_failures: int = 0
    websocket_failures: int = 0
    ai_latency_ms: float = 0.0
    analytics_latency_ms: float = 0.0
    order_validation_latency_ms: float = 0.0
    cache_hit_ratio: float = 0.0
    recovery_time_ms: float = 0.0

    def to_public_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class StateSnapshot:
    id: str
    created_at: datetime
    payload: dict[str, Any]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "payload": self.payload,
        }
