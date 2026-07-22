from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal

Severity = Literal["info", "warning", "error", "critical"]
Category = Literal["trade", "risk", "broker", "ai", "portfolio", "system"]
RiskState = Literal["NORMAL", "WARNING", "CRITICAL"]


@dataclass(frozen=True)
class TradeAnalytics:
    id: str
    asset: str
    strategy: str | None
    side: str
    entry_price: Decimal
    exit_price: Decimal | None
    quantity: Decimal
    notional: Decimal
    entry_fee: Decimal
    exit_fee: Decimal
    total_fee: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
    return_pct: Decimal
    holding_time: timedelta | None
    close_reason: str | None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    trailing_stop: Decimal | None = None
    ai_decision: str | None = None
    ai_confidence: int | None = None
    market_regime: str | None = None
    broker: str | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    status: str = "closed"

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self)


@dataclass(frozen=True)
class PerformanceSummary:
    starting_equity: Decimal = Decimal("0")
    ending_equity: Decimal = Decimal("0")
    net_profit: Decimal = Decimal("0")
    gross_profit: Decimal = Decimal("0")
    gross_loss: Decimal = Decimal("0")
    total_return_pct: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    total_fees: Decimal = Decimal("0")
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    win_rate: Decimal = Decimal("0")
    loss_rate: Decimal = Decimal("0")
    profit_factor: Decimal = Decimal("0")
    expectancy: Decimal = Decimal("0")
    average_trade: Decimal = Decimal("0")
    average_win: Decimal = Decimal("0")
    average_loss: Decimal = Decimal("0")
    payoff_ratio: Decimal = Decimal("0")
    largest_win: Decimal = Decimal("0")
    largest_loss: Decimal = Decimal("0")
    maximum_drawdown: Decimal = Decimal("0")
    maximum_drawdown_pct: Decimal = Decimal("0")
    current_drawdown: Decimal = Decimal("0")
    current_drawdown_pct: Decimal = Decimal("0")
    recovery_factor: Decimal = Decimal("0")
    average_holding_time: float = 0.0
    longest_holding_time: float = 0.0
    shortest_holding_time: float = 0.0
    sharpe: Decimal = Decimal("0")
    sortino: Decimal = Decimal("0")
    calmar: Decimal = Decimal("0")
    consecutive_wins: int = 0
    consecutive_losses: int = 0

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self)


@dataclass(frozen=True)
class EquityPoint:
    timestamp: datetime
    cash: Decimal
    equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    cumulative_pnl: Decimal
    cumulative_return_pct: Decimal
    drawdown: Decimal
    drawdown_pct: Decimal

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self)


@dataclass(frozen=True)
class DrawdownPoint:
    start_at: datetime | None
    valley_at: datetime | None
    recovered_at: datetime | None
    drawdown: Decimal
    drawdown_pct: Decimal
    duration_seconds: float
    recovered: bool

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self)


@dataclass(frozen=True)
class StrategyPerformance:
    strategy: str
    summary: PerformanceSummary
    contribution_pct: Decimal
    composite_score: Decimal

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "summary": self.summary.to_public_dict(),
            "contribution_pct": float(self.contribution_pct),
            "composite_score": float(self.composite_score),
        }


@dataclass(frozen=True)
class AssetPerformance:
    asset: str
    summary: PerformanceSummary
    capital_used: Decimal
    average_exposure: Decimal
    max_exposure: Decimal
    contribution_pct: Decimal

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self)


@dataclass(frozen=True)
class AIAttribution:
    decision: str
    decisions: int
    executed: int
    rejected: int
    no_operation: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    pnl: Decimal
    average_confidence: Decimal
    winning_confidence: Decimal
    losing_confidence: Decimal
    market_regime_distribution: dict[str, int]
    risk_distribution: dict[str, int]
    confidence_buckets: dict[str, int]

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self)


@dataclass(frozen=True)
class RiskAttribution:
    total_exposure: Decimal
    exposure_by_asset: dict[str, Decimal]
    exposure_by_strategy: dict[str, Decimal]
    exposure_by_broker: dict[str, Decimal]
    capital_at_risk: Decimal
    fees: Decimal
    realized_losses: Decimal
    unrealized_losses: Decimal
    drawdown: Decimal
    blocked_operations: int
    rejection_reasons: dict[str, int]
    limit_utilization: dict[str, Decimal]
    concentration_pct: Decimal
    state: RiskState

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self)


@dataclass(frozen=True)
class BrokerPerformance:
    broker: str
    requests: int
    accepted_orders: int
    rejected_orders: int
    cancelled_orders: int
    errors: int
    avg_latency_ms: float | None
    min_latency_ms: float | None
    max_latency_ms: float | None
    success_rate: Decimal
    rejection_rate: Decimal
    last_error: str | None
    last_event: str | None
    connected: bool
    connected_seconds: float | None
    notes: tuple[str, ...] = tuple()

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self)


@dataclass(frozen=True)
class TimeBucketPerformance:
    bucket: str
    trades: int
    pnl: Decimal
    win_rate: Decimal
    average_trade: Decimal
    fees: Decimal
    exposure: Decimal
    holding_time: float

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self)


@dataclass(frozen=True)
class AnalyticsEvent:
    timestamp: datetime
    category: Category
    event_type: str
    severity: Severity
    source: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self)


def _public(obj: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in obj.__dict__.items():
        if isinstance(value, Decimal):
            data[key] = float(value) if value.is_finite() else 0.0
        elif isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, timedelta):
            data[key] = value.total_seconds()
        elif isinstance(value, dict):
            data[key] = {
                k: (float(v) if isinstance(v, Decimal) else v) for k, v in value.items()
            }
        elif hasattr(value, "to_public_dict"):
            data[key] = value.to_public_dict()
        else:
            data[key] = value
    return data


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
