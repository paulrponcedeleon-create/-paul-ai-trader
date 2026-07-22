from __future__ import annotations

from collections import Counter
from decimal import Decimal

from app.analytics.models import AIAttribution, AnalyticsEvent, TradeAnalytics
from app.analytics.performance import D, q

BUCKETS = [
    (0, 20, "0-20"),
    (21, 40, "21-40"),
    (41, 60, "41-60"),
    (61, 80, "61-80"),
    (81, 100, "81-100"),
]


class AIAttributionEngine:
    def calculate(
        self, trades: list[TradeAnalytics], events: list[AnalyticsEvent] | None = None
    ) -> list[AIAttribution]:
        events = events or []
        decisions = ["buy", "sell", "hold"]
        rows = []
        for decision in decisions:
            decision_events = [
                e
                for e in events
                if e.category == "ai" and e.metadata.get("decision") == decision
            ]
            linked_trades = [
                t for t in trades if (t.ai_decision or "").lower() == decision
            ]
            wins = [t for t in linked_trades if D(t.net_pnl) > 0]
            losses = [t for t in linked_trades if D(t.net_pnl) < 0]
            confidences = [Decimal(t.ai_confidence or 0) for t in linked_trades]
            rows.append(
                AIAttribution(
                    decision,
                    len(decision_events) or len(linked_trades),
                    len(linked_trades),
                    sum(
                        1
                        for e in decision_events
                        if e.metadata.get("status") == "rejected"
                    ),
                    max((len(decision_events) - len(linked_trades)), 0),
                    len(wins),
                    len(losses),
                    q(Decimal(len(wins)) / Decimal(len(linked_trades)) * Decimal("100"))
                    if linked_trades
                    else Decimal("0"),
                    q(sum((D(t.net_pnl) for t in linked_trades), Decimal("0"))),
                    q(sum(confidences, Decimal("0")) / Decimal(len(confidences)))
                    if confidences
                    else Decimal("0"),
                    _avg_conf(wins),
                    _avg_conf(losses),
                    dict(Counter(t.market_regime or "unknown" for t in linked_trades)),
                    dict(
                        Counter(
                            e.metadata.get("risk", "unknown") for e in decision_events
                        )
                    ),
                    _confidence_buckets(confidences),
                )
            )
        return rows


def _avg_conf(trades: list[TradeAnalytics]) -> Decimal:
    values = [Decimal(t.ai_confidence or 0) for t in trades]
    return (
        q(sum(values, Decimal("0")) / Decimal(len(values))) if values else Decimal("0")
    )


def _confidence_buckets(values: list[Decimal]) -> dict[str, int]:
    result = {label: 0 for _, _, label in BUCKETS}
    for value in values:
        for low, high, label in BUCKETS:
            if Decimal(low) <= value <= Decimal(high):
                result[label] += 1
                break
    return result
