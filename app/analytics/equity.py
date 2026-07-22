from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.analytics.models import DrawdownPoint, EquityPoint, TradeAnalytics
from app.analytics.performance import D, q


class EquityCurveEngine:
    def build(
        self, trades: list[TradeAnalytics], *, starting_equity: Decimal = Decimal("0")
    ) -> list[EquityPoint]:
        items = sorted(trades, key=lambda t: t.closed_at or t.opened_at or datetime.min)
        if any(
            (items[i].closed_at or items[i].opened_at or datetime.min)
            > (items[i + 1].closed_at or items[i + 1].opened_at or datetime.min)
            for i in range(len(items) - 1)
        ):
            raise ValueError("Trades fuera de orden cronológico.")
        equity = D(starting_equity)
        peak = equity
        points: list[EquityPoint] = []
        for trade in items:
            equity += D(trade.net_pnl)
            peak = max(peak, equity)
            drawdown = max(peak - equity, Decimal("0"))
            points.append(
                EquityPoint(
                    trade.closed_at or trade.opened_at or datetime.min,
                    equity,
                    equity,
                    D(trade.net_pnl),
                    Decimal("0"),
                    equity - D(starting_equity),
                    q(
                        (
                            (equity - D(starting_equity))
                            / D(starting_equity)
                            * Decimal("100")
                        )
                        if D(starting_equity)
                        else Decimal("0")
                    ),
                    drawdown,
                    q((drawdown / peak * Decimal("100")) if peak else Decimal("0")),
                )
            )
        return points

    def drawdowns(self, points: list[EquityPoint]) -> list[DrawdownPoint]:
        result: list[DrawdownPoint] = []
        peak = None
        start = None
        valley = None
        max_dd = Decimal("0")
        for point in points:
            if peak is None or point.equity >= peak.equity:
                if start is not None:
                    result.append(
                        DrawdownPoint(
                            start.timestamp,
                            valley.timestamp if valley else None,
                            point.timestamp,
                            max_dd,
                            q(
                                (max_dd / peak.equity * Decimal("100"))
                                if peak and peak.equity
                                else Decimal("0")
                            ),
                            (point.timestamp - start.timestamp).total_seconds(),
                            True,
                        )
                    )
                peak = point
                start = None
                valley = None
                max_dd = Decimal("0")
                continue
            dd = peak.equity - point.equity
            if start is None:
                start = peak
            if dd > max_dd:
                max_dd = dd
                valley = point
        if start is not None:
            last = points[-1]
            result.append(
                DrawdownPoint(
                    start.timestamp,
                    valley.timestamp if valley else None,
                    None,
                    max_dd,
                    q(
                        (max_dd / peak.equity * Decimal("100"))
                        if peak and peak.equity
                        else Decimal("0")
                    ),
                    (last.timestamp - start.timestamp).total_seconds(),
                    False,
                )
            )
        return result
