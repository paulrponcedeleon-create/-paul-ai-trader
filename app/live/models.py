from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]
AuditResult = Literal[
    "accepted", "rejected", "error", "cancelled", "filled", "partial_fill"
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class LiveOrderRequest:
    book: str
    side: OrderSide
    order_type: OrderType
    amount_mxn: Decimal
    price: Decimal | None = None
    user: str = "system"
    strategy: str | None = None
    ai_decision: str | None = None
    confidence: int | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "book": self.book,
            "side": self.side,
            "order_type": self.order_type,
            "amount_mxn": float(self.amount_mxn),
            "price": float(self.price) if self.price is not None else None,
            "user": self.user,
            "strategy": self.strategy,
            "ai_decision": self.ai_decision,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class GuardCheck:
    name: str
    passed: bool
    reason: str

    def to_public_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "reason": self.reason}


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    checks: tuple[GuardCheck, ...]

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(check.reason for check in self.checks if not check.passed)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "checks": [check.to_public_dict() for check in self.checks],
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ExecutionAuditRecord:
    timestamp: datetime
    user: str
    strategy: str | None
    ai_decision: str | None
    confidence: int | None
    book: str
    amount_mxn: Decimal
    broker: str
    result: AuditResult
    reason: str
    response: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "user": self.user,
            "strategy": self.strategy,
            "ai_decision": self.ai_decision,
            "confidence": self.confidence,
            "book": self.book,
            "amount_mxn": float(self.amount_mxn),
            "broker": self.broker,
            "result": self.result,
            "reason": self.reason,
            "response": self.response,
        }
