from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.services.backtest_metrics import round_money, round_pct, to_decimal


class InsufficientFundsError(Exception):
    pass


@dataclass(frozen=True)
class Position:
    opened_at: datetime
    entry_price: Decimal
    quantity: Decimal
    amount_mxn: Decimal
    entry_fee_mxn: Decimal
    signal_data: dict[str, Any]


@dataclass(frozen=True)
class BacktestTradeResult:
    opened_at: datetime
    closed_at: datetime
    book: str
    side: str
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    amount_mxn: Decimal
    pnl_mxn: Decimal
    return_pct: Decimal
    fees_mxn: Decimal
    signal_data: dict[str, Any]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat(),
            "book": self.book,
            "side": self.side,
            "entry_price": float(self.entry_price),
            "exit_price": float(self.exit_price),
            "quantity": float(self.quantity),
            "amount_mxn": float(self.amount_mxn),
            "pnl_mxn": float(self.pnl_mxn),
            "return_pct": float(self.return_pct),
            "fees_mxn": float(self.fees_mxn),
            "signal_data": self.signal_data,
        }


class BrokerSimulator:
    def __init__(self, *, initial_capital_mxn: Decimal, fee_rate: Decimal) -> None:
        if initial_capital_mxn <= 0:
            raise ValueError("El capital inicial debe ser mayor que cero.")
        if fee_rate < 0:
            raise ValueError("La comisión no puede ser negativa.")
        self.initial_capital_mxn = round_money(initial_capital_mxn)
        self.cash_mxn = round_money(initial_capital_mxn)
        self.fee_rate = fee_rate
        self.position: Position | None = None
        self.trades: list[BacktestTradeResult] = []

    @property
    def has_position(self) -> bool:
        return self.position is not None

    def buy(
        self,
        *,
        opened_at: datetime,
        price: Decimal,
        amount_mxn: Decimal,
        signal_data: dict[str, Any],
    ) -> Position:
        price = to_decimal(price)
        amount = round_money(amount_mxn)
        if price <= 0 or amount <= 0:
            raise ValueError("Precio y monto deben ser positivos.")
        if self.position is not None:
            return self.position
        entry_fee = round_money(amount * self.fee_rate)
        total_cost = amount + entry_fee
        if total_cost > self.cash_mxn:
            raise InsufficientFundsError("Fondos insuficientes para abrir la posición.")
        quantity = (amount / price) if price else Decimal("0")
        self.cash_mxn = round_money(self.cash_mxn - total_cost)
        self._assert_non_negative_cash()
        self.position = Position(
            opened_at=opened_at,
            entry_price=price,
            quantity=quantity,
            amount_mxn=amount,
            entry_fee_mxn=entry_fee,
            signal_data=dict(signal_data),
        )
        return self.position

    def close(
        self,
        *,
        closed_at: datetime,
        price: Decimal,
        book: str,
        signal_data: dict[str, Any],
    ) -> BacktestTradeResult | None:
        if self.position is None:
            return None
        price = to_decimal(price)
        if price <= 0:
            raise ValueError("El precio de cierre debe ser positivo.")
        position = self.position
        gross_exit = position.quantity * price
        exit_fee = round_money(gross_exit * self.fee_rate)
        net_exit = round_money(gross_exit - exit_fee)
        pnl = round_money(net_exit - position.amount_mxn - position.entry_fee_mxn)
        invested = position.amount_mxn + position.entry_fee_mxn
        return_pct = (
            Decimal("0")
            if invested == 0
            else round_pct((pnl / invested) * Decimal("100"))
        )
        self.cash_mxn = round_money(self.cash_mxn + net_exit)
        self._assert_non_negative_cash()
        trade = BacktestTradeResult(
            opened_at=position.opened_at,
            closed_at=closed_at,
            book=book,
            side="buy",
            entry_price=position.entry_price,
            exit_price=price,
            quantity=position.quantity,
            amount_mxn=position.amount_mxn,
            pnl_mxn=pnl,
            return_pct=return_pct,
            fees_mxn=round_money(position.entry_fee_mxn + exit_fee),
            signal_data={"entry": position.signal_data, "exit": dict(signal_data)},
        )
        self.trades.append(trade)
        self.position = None
        return trade

    def equity(self, current_price: Decimal | None = None) -> Decimal:
        if self.position is None or current_price is None:
            return round_money(self.cash_mxn)
        gross_value = self.position.quantity * to_decimal(current_price)
        estimated_exit_fee = round_money(gross_value * self.fee_rate)
        return round_money(self.cash_mxn + gross_value - estimated_exit_fee)

    def available_cash(self) -> Decimal:
        return self.cash_mxn

    def _assert_non_negative_cash(self) -> None:
        if self.cash_mxn < 0:
            raise AssertionError("El broker simulado generó capital negativo.")
