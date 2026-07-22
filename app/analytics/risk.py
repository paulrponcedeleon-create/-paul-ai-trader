from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal

from app.analytics.models import AnalyticsEvent, RiskAttribution, TradeAnalytics
from app.analytics.performance import D, q


@dataclass(frozen=True)
class RiskThresholds:
    warning_exposure_pct: Decimal = Decimal("60")
    critical_exposure_pct: Decimal = Decimal("85")
    warning_drawdown_pct: Decimal = Decimal("10")
    critical_drawdown_pct: Decimal = Decimal("20")


class RiskAttributionEngine:
    def __init__(self, thresholds: RiskThresholds | None = None) -> None:
        self.thresholds = thresholds or RiskThresholds()

    def calculate(
        self,
        trades: list[TradeAnalytics],
        events: list[AnalyticsEvent] | None = None,
        *,
        equity: Decimal = Decimal("0"),
    ) -> RiskAttribution:
        events = events or []
        exposure_by_asset: dict[str, Decimal] = defaultdict(Decimal)
        exposure_by_strategy: dict[str, Decimal] = defaultdict(Decimal)
        exposure_by_broker: dict[str, Decimal] = defaultdict(Decimal)
        for trade in trades:
            exposure_by_asset[trade.asset] += D(trade.notional)
            exposure_by_strategy[trade.strategy or "unknown"] += D(trade.notional)
            exposure_by_broker[trade.broker or "unknown"] += D(trade.notional)
        total = sum(exposure_by_asset.values(), Decimal("0"))
        losses = abs(
            sum((D(t.net_pnl) for t in trades if D(t.net_pnl) < 0), Decimal("0"))
        )
        rejected = [
            e for e in events if e.category == "risk" and e.event_type == "blocked"
        ]
        concentration = q(
            (max(exposure_by_asset.values()) / total * Decimal("100"))
            if total and exposure_by_asset
            else Decimal("0")
        )
        utilization = {
            "exposure_pct": q(
                (total / equity * Decimal("100")) if equity else Decimal("0")
            )
        }
        state = (
            "CRITICAL"
            if utilization["exposure_pct"] >= self.thresholds.critical_exposure_pct
            else "WARNING"
            if utilization["exposure_pct"] >= self.thresholds.warning_exposure_pct
            else "NORMAL"
        )
        return RiskAttribution(
            total,
            dict(exposure_by_asset),
            dict(exposure_by_strategy),
            dict(exposure_by_broker),
            total,
            sum((D(t.total_fee) for t in trades), Decimal("0")),
            losses,
            Decimal("0"),
            Decimal("0"),
            len(rejected),
            dict(Counter(e.message for e in rejected)),
            utilization,
            concentration,
            state,
        )
