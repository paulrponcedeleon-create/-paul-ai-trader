from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from app.analytics.models import (
    AssetPerformance,
    StrategyPerformance,
    TimeBucketPerformance,
    TradeAnalytics,
)
from app.analytics.performance import PerformanceAnalyticsEngine, D, q


class AttributionEngine:
    def __init__(self) -> None:
        self.performance = PerformanceAnalyticsEngine()

    def by_strategy(
        self, trades: list[TradeAnalytics], *, starting_equity: Decimal = Decimal("0")
    ) -> list[StrategyPerformance]:
        total = sum((D(t.net_pnl) for t in trades), Decimal("0"))
        grouped: dict[str, list[TradeAnalytics]] = defaultdict(list)
        for trade in trades:
            grouped[trade.strategy or "unknown"].append(trade)
        rows = []
        for strategy, items in grouped.items():
            summary = self.performance.summarize(items, starting_equity=starting_equity)
            contribution = q(
                (summary.net_profit / total * Decimal("100")) if total else Decimal("0")
            )
            score = q(
                summary.net_profit
                + summary.expectancy
                + summary.sharpe
                - summary.maximum_drawdown
            )
            rows.append(StrategyPerformance(strategy, summary, contribution, score))
        return sorted(rows, key=lambda row: row.composite_score, reverse=True)

    def by_asset(
        self, trades: list[TradeAnalytics], *, starting_equity: Decimal = Decimal("0")
    ) -> list[AssetPerformance]:
        total = sum((D(t.net_pnl) for t in trades), Decimal("0"))
        grouped: dict[str, list[TradeAnalytics]] = defaultdict(list)
        for trade in trades:
            grouped[trade.asset].append(trade)
        rows = []
        for asset, items in grouped.items():
            summary = self.performance.summarize(items, starting_equity=starting_equity)
            exposure = [D(t.notional) for t in items]
            rows.append(
                AssetPerformance(
                    asset,
                    summary,
                    sum(exposure, Decimal("0")),
                    q(sum(exposure, Decimal("0")) / Decimal(len(exposure)))
                    if exposure
                    else Decimal("0"),
                    max(exposure) if exposure else Decimal("0"),
                    q(
                        (summary.net_profit / total * Decimal("100"))
                        if total
                        else Decimal("0")
                    ),
                )
            )
        return sorted(rows, key=lambda row: row.summary.net_profit, reverse=True)

    def time_buckets(
        self, trades: list[TradeAnalytics], period: str = "day"
    ) -> list[TimeBucketPerformance]:
        grouped: dict[str, list[TradeAnalytics]] = defaultdict(list)
        for trade in trades:
            ts = trade.closed_at or trade.opened_at
            if ts is None:
                key = "unknown"
            elif period == "hour":
                key = f"hour:{ts.hour:02d}"
            elif period == "weekday":
                key = f"weekday:{ts.weekday()}"
            elif period == "week":
                year, week, _ = ts.isocalendar()
                key = f"{year}-W{week:02d}"
            elif period == "month":
                key = ts.strftime("%Y-%m")
            else:
                key = ts.strftime("%Y-%m-%d")
            grouped[key].append(trade)
        rows = []
        for key, items in grouped.items():
            summary = self.performance.summarize(items)
            holding = [t.holding_time.total_seconds() for t in items if t.holding_time]
            rows.append(
                TimeBucketPerformance(
                    key,
                    len(items),
                    summary.net_profit,
                    summary.win_rate,
                    summary.average_trade,
                    summary.total_fees,
                    sum((D(t.notional) for t in items), Decimal("0")),
                    sum(holding) / len(holding) if holding else 0.0,
                )
            )
        return sorted(rows, key=lambda row: row.bucket)
