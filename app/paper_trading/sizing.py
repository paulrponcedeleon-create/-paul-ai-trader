from __future__ import annotations

from decimal import Decimal

from app.services.backtest_metrics import round_money, to_decimal


class PositionSizer:
    def calculate(
        self,
        *,
        method: str,
        value: Decimal | int | float | str,
        equity_mxn: Decimal,
        cash_mxn: Decimal,
        risk_per_trade_pct: Decimal = Decimal("1"),
    ) -> Decimal:
        raw = to_decimal(value)
        if raw <= 0:
            raise ValueError("El tamaño de posición debe ser positivo.")
        if method == "fixed_size":
            amount = raw
        elif method == "fixed_fractional":
            amount = (
                equity_mxn
                * (raw / Decimal("100"))
                * (risk_per_trade_pct / Decimal("100"))
            )
        elif method == "percentage_of_equity":
            amount = equity_mxn * (raw / Decimal("100"))
        else:
            raise ValueError("Método de position sizing no soportado.")
        return round_money(min(amount, cash_mxn))
