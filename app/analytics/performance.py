from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from math import sqrt
from typing import Any

from app.analytics.models import PerformanceSummary, TradeAnalytics

Q = Decimal("0.0001")


def D(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value if value.is_finite() else Decimal("0")
    try:
        result = Decimal(str(value))
    except Exception:
        return Decimal("0")
    return result if result.is_finite() else Decimal("0")


def q(value: Decimal) -> Decimal:
    return value.quantize(Q, rounding=ROUND_HALF_UP)


class PerformanceAnalyticsEngine:
    def summarize(
        self,
        trades: Iterable[TradeAnalytics],
        *,
        starting_equity: Decimal | int | float | str = Decimal("0"),
        ending_equity: Decimal | int | float | str | None = None,
    ) -> PerformanceSummary:
        items = sorted(
            list(trades), key=lambda t: t.closed_at or t.opened_at or datetime.min
        )
        start = D(starting_equity)
        net_values = [D(t.net_pnl) for t in items]
        gross_profit = sum((v for v in net_values if v > 0), Decimal("0"))
        gross_loss = abs(sum((v for v in net_values if v < 0), Decimal("0")))
        net_profit = gross_profit - gross_loss
        end = D(ending_equity) if ending_equity is not None else start + net_profit
        wins = [v for v in net_values if v > 0]
        losses = [v for v in net_values if v < 0]
        breakeven = [v for v in net_values if v == 0]
        count = len(items)
        total_fees = sum((D(t.total_fee) for t in items), Decimal("0"))
        holding = [t.holding_time.total_seconds() for t in items if t.holding_time]
        returns = [D(t.return_pct) for t in items]
        max_dd, max_dd_pct, current_dd, current_dd_pct = _drawdown_from_returns(
            start, net_values
        )
        return PerformanceSummary(
            starting_equity=q(start),
            ending_equity=q(end),
            net_profit=q(net_profit),
            gross_profit=q(gross_profit),
            gross_loss=q(gross_loss),
            total_return_pct=q(
                ((end - start) / start * Decimal("100")) if start else Decimal("0")
            ),
            realized_pnl=q(net_profit),
            unrealized_pnl=Decimal("0"),
            total_fees=q(total_fees),
            total_trades=count,
            winning_trades=len(wins),
            losing_trades=len(losses),
            breakeven_trades=len(breakeven),
            win_rate=q(Decimal(len(wins)) / Decimal(count) * Decimal("100"))
            if count
            else Decimal("0"),
            loss_rate=q(Decimal(len(losses)) / Decimal(count) * Decimal("100"))
            if count
            else Decimal("0"),
            profit_factor=q(gross_profit / gross_loss)
            if gross_loss
            else (q(gross_profit) if gross_profit else Decimal("0")),
            expectancy=q(net_profit / Decimal(count)) if count else Decimal("0"),
            average_trade=q(net_profit / Decimal(count)) if count else Decimal("0"),
            average_win=q(sum(wins, Decimal("0")) / Decimal(len(wins)))
            if wins
            else Decimal("0"),
            average_loss=q(abs(sum(losses, Decimal("0"))) / Decimal(len(losses)))
            if losses
            else Decimal("0"),
            payoff_ratio=q(
                (sum(wins, Decimal("0")) / Decimal(len(wins)))
                / (abs(sum(losses, Decimal("0"))) / Decimal(len(losses)))
            )
            if wins and losses
            else Decimal("0"),
            largest_win=q(max(wins)) if wins else Decimal("0"),
            largest_loss=q(abs(min(losses))) if losses else Decimal("0"),
            maximum_drawdown=q(max_dd),
            maximum_drawdown_pct=q(max_dd_pct),
            current_drawdown=q(current_dd),
            current_drawdown_pct=q(current_dd_pct),
            recovery_factor=q(net_profit / max_dd) if max_dd else Decimal("0"),
            average_holding_time=sum(holding) / len(holding) if holding else 0.0,
            longest_holding_time=max(holding) if holding else 0.0,
            shortest_holding_time=min(holding) if holding else 0.0,
            sharpe=q(_sharpe(returns)),
            sortino=q(_sortino(returns)),
            calmar=q(
                (((end - start) / start * Decimal("100")) if start else Decimal("0"))
                / max_dd_pct
            )
            if max_dd_pct
            else Decimal("0"),
            consecutive_wins=_longest_streak(net_values, True),
            consecutive_losses=_longest_streak(net_values, False),
        )

    def filter_trades(
        self, trades: Iterable[TradeAnalytics], **filters: Any
    ) -> list[TradeAnalytics]:
        result = list(trades)
        start = filters.get("start")
        end = filters.get("end")
        assets = set(
            filters.get("assets")
            or ([filters["asset"]] if filters.get("asset") else [])
        )
        strategies = set(
            filters.get("strategies")
            or ([filters["strategy"]] if filters.get("strategy") else [])
        )
        for key, attr in [
            ("broker", "broker"),
            ("ai_decision", "ai_decision"),
            ("close_reason", "close_reason"),
            ("status", "status"),
            ("side", "side"),
        ]:
            value = filters.get(key)
            if value is not None:
                result = [t for t in result if getattr(t, attr) == value]
        if start is not None:
            result = [
                t for t in result if t.opened_at is not None and t.opened_at >= start
            ]
        if end is not None:
            result = [
                t for t in result if t.closed_at is not None and t.closed_at <= end
            ]
        if assets:
            result = [t for t in result if t.asset in assets]
        if strategies:
            result = [t for t in result if t.strategy in strategies]
        return result


def _drawdown_from_returns(
    start: Decimal, pnl_values: list[Decimal]
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    equity = start
    peak = start
    max_dd = Decimal("0")
    current = Decimal("0")
    for pnl in pnl_values:
        equity += pnl
        if equity > peak:
            peak = equity
        current = max(peak - equity, Decimal("0"))
        max_dd = max(max_dd, current)
    max_pct = (max_dd / peak * Decimal("100")) if peak else Decimal("0")
    current_pct = (current / peak * Decimal("100")) if peak else Decimal("0")
    return max_dd, max_pct, current, current_pct


def _sharpe(returns: list[Decimal]) -> Decimal:
    if len(returns) < 2:
        return Decimal("0")
    mean = sum(returns, Decimal("0")) / Decimal(len(returns))
    variance = sum((r - mean) ** 2 for r in returns) / Decimal(len(returns))
    return (
        Decimal(str(float(mean) / sqrt(float(variance)))) if variance else Decimal("0")
    )


def _sortino(returns: list[Decimal]) -> Decimal:
    downside = [r for r in returns if r < 0]
    if not downside:
        return Decimal("0")
    mean = sum(returns, Decimal("0")) / Decimal(len(returns))
    variance = sum((r) ** 2 for r in downside) / Decimal(len(downside))
    return (
        Decimal(str(float(mean) / sqrt(float(variance)))) if variance else Decimal("0")
    )


def _longest_streak(values: list[Decimal], wins: bool) -> int:
    best = current = 0
    for value in values:
        ok = value > 0 if wins else value < 0
        current = current + 1 if ok else 0
        best = max(best, current)
    return best
