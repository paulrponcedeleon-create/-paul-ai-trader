from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 30.0
    state: str = "CLOSED"
    failures: int = 0
    opened_at: float | None = None

    def record_success(self) -> None:
        self.failures = 0
        self.state = "CLOSED"
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            self.opened_at = monotonic()

    def allow_request(self) -> bool:
        if self.state == "CLOSED":
            return True
        if (
            self.state == "OPEN"
            and self.opened_at is not None
            and monotonic() - self.opened_at >= self.recovery_timeout_seconds
        ):
            self.state = "HALF_OPEN"
            return True
        return self.state == "HALF_OPEN"

    def to_public_dict(self) -> dict:
        return {"name": self.name, "state": self.state, "failures": self.failures}


class CircuitBreakerManager:
    def __init__(self) -> None:
        self.breakers = {
            name: CircuitBreaker(name)
            for name in ["Market Data", "Broker", "AI", "Analytics"]
        }

    def status(self) -> dict[str, dict]:
        return {
            name: breaker.to_public_dict() for name, breaker in self.breakers.items()
        }
