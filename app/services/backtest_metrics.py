from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

MONEY_QUANT = Decimal("0.01")
PCT_QUANT = Decimal("0.0001")


def to_decimal(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def round_money(value: Decimal | int | float | str) -> Decimal:
    return to_decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def round_pct(value: Decimal | int | float | str) -> Decimal:
    return to_decimal(value).quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class BacktestMetrics:
    initial_capital_mxn: Decimal
    final_capital_mxn: Decimal
    total_return_pct: Decimal
    max_drawdown_pct: Decimal
    win_rate_pct: Decimal
    trades_count: int
    winning_trades: int
    losing_trades: int
    total_fees_mxn: Decimal
    gross_profit_mxn: Decimal
    gross_loss_mxn: Decimal
    profit_factor: Decimal | None
    average_trade_return_pct: Decimal
    average_win_mxn: Decimal
    average_loss_mxn: Decimal
    largest_win_mxn: Decimal
    largest_loss_mxn: Decimal
    expectancy_mxn: Decimal
    exposure_pct: Decimal
    equity_curve: tuple[dict[str, Any], ...]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "initial_capital_mxn": float(self.initial_capital_mxn),
            "final_capital_mxn": float(self.final_capital_mxn),
            "total_return_pct": float(self.total_return_pct),
            "max_drawdown_pct": float(self.max_drawdown_pct),
            "win_rate_pct": float(self.win_rate_pct),
            "trades_count": self.trades_count,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_fees_mxn": float(self.total_fees_mxn),
            "gross_profit_mxn": float(self.gross_profit_mxn),
            "gross_loss_mxn": float(self.gross_loss_mxn),
            "profit_factor": float(self.profit_factor)
            if self.profit_factor is not None
            else None,
            "average_trade_return_pct": float(self.average_trade_return_pct),
            "average_win_mxn": float(self.average_win_mxn),
            "average_loss_mxn": float(self.average_loss_mxn),
            "largest_win_mxn": float(self.largest_win_mxn),
            "largest_loss_mxn": float(self.largest_loss_mxn),
            "expectancy_mxn": float(self.expectancy_mxn),
            "exposure_pct": float(self.exposure_pct),
            "equity_curve": list(self.equity_curve),
        }


def calculate_backtest_metrics(
    *,
    initial_capital_mxn: Decimal,
    final_capital_mxn: Decimal,
    trades: list[Any],
    equity_curve: list[dict[str, Any]],
    exposure_periods: int,
    total_periods: int,
) -> BacktestMetrics:
    initial = round_money(initial_capital_mxn)
    final = round_money(final_capital_mxn)
    trade_count = len(trades)
    pnl_values = [to_decimal(trade.pnl_mxn) for trade in trades]
    winning = [pnl for pnl in pnl_values if pnl > 0]
    losing = [pnl for pnl in pnl_values if pnl < 0]

    gross_profit = round_money(sum(winning, Decimal("0")))
    gross_loss_abs = round_money(abs(sum(losing, Decimal("0"))))
    total_fees = round_money(
        sum((to_decimal(trade.fees_mxn) for trade in trades), Decimal("0"))
    )

    if initial == 0:
        total_return = Decimal("0")
    else:
        total_return = round_pct(((final - initial) / initial) * Decimal("100"))

    win_rate = (
        Decimal("0")
        if trade_count == 0
        else round_pct((Decimal(len(winning)) / Decimal(trade_count)) * Decimal("100"))
    )
    profit_factor = None if gross_loss_abs == 0 and gross_profit > 0 else Decimal("0")
    if gross_loss_abs > 0:
        profit_factor = round_pct(gross_profit / gross_loss_abs)
    elif gross_profit == 0:
        profit_factor = Decimal("0")

    avg_return = Decimal("0")
    if trade_count:
        avg_return = round_pct(
            sum((to_decimal(trade.return_pct) for trade in trades), Decimal("0"))
            / Decimal(trade_count)
        )

    avg_win = (
        round_money(sum(winning, Decimal("0")) / Decimal(len(winning)))
        if winning
        else Decimal("0.00")
    )
    avg_loss = (
        round_money(abs(sum(losing, Decimal("0"))) / Decimal(len(losing)))
        if losing
        else Decimal("0.00")
    )
    largest_win = round_money(max(winning)) if winning else Decimal("0.00")
    largest_loss = round_money(abs(min(losing))) if losing else Decimal("0.00")
    expectancy = Decimal("0.00")
    if trade_count:
        expectancy = round_money(sum(pnl_values, Decimal("0")) / Decimal(trade_count))

    exposure = Decimal("0")
    if total_periods > 0:
        exposure = round_pct(
            (Decimal(exposure_periods) / Decimal(total_periods)) * Decimal("100")
        )

    return BacktestMetrics(
        initial_capital_mxn=initial,
        final_capital_mxn=final,
        total_return_pct=total_return,
        max_drawdown_pct=_max_drawdown(equity_curve),
        win_rate_pct=win_rate,
        trades_count=trade_count,
        winning_trades=len(winning),
        losing_trades=len(losing),
        total_fees_mxn=total_fees,
        gross_profit_mxn=gross_profit,
        gross_loss_mxn=gross_loss_abs,
        profit_factor=profit_factor,
        average_trade_return_pct=avg_return,
        average_win_mxn=avg_win,
        average_loss_mxn=avg_loss,
        largest_win_mxn=largest_win,
        largest_loss_mxn=largest_loss,
        expectancy_mxn=expectancy,
        exposure_pct=exposure,
        equity_curve=tuple(equity_curve),
    )


def _max_drawdown(equity_curve: list[dict[str, Any]]) -> Decimal:
    if not equity_curve:
        return Decimal("0.0000")
    peak: Decimal | None = None
    max_drawdown = Decimal("0")
    for point in equity_curve:
        equity = to_decimal(point["equity_mxn"])
        if peak is None or equity > peak:
            peak = equity
        if peak and peak > 0:
            drawdown = ((peak - equity) / peak) * Decimal("100")
            if drawdown > max_drawdown:
                max_drawdown = drawdown
    return round_pct(max_drawdown)
