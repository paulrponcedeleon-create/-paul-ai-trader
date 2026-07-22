from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import itertools
from typing import Any

from app.paper_trading.models import PaperOrder, PaperPosition, PaperTrade, utc_now
from app.services.backtest_metrics import round_money, round_pct, to_decimal
from app.services.broker_simulator import BrokerSimulator, InsufficientFundsError


@dataclass
class PortfolioSnapshot:
    cash_mxn: Decimal
    equity_mxn: Decimal
    realized_pnl_mxn: Decimal
    unrealized_pnl_mxn: Decimal
    max_drawdown_pct: Decimal
    open_positions: tuple[PaperPosition, ...]
    closed_positions: tuple[PaperPosition, ...]
    orders: tuple[PaperOrder, ...]
    trades: tuple[PaperTrade, ...]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "cash_mxn": float(self.cash_mxn),
            "equity_mxn": float(self.equity_mxn),
            "realized_pnl_mxn": float(self.realized_pnl_mxn),
            "unrealized_pnl_mxn": float(self.unrealized_pnl_mxn),
            "max_drawdown_pct": float(self.max_drawdown_pct),
            "open_positions": len(self.open_positions),
            "closed_positions": len(self.closed_positions),
            "orders": len(self.orders),
            "trades": [trade.to_public_dict() for trade in self.trades],
        }


class PortfolioManager:
    def __init__(self, *, initial_cash_mxn: Decimal | int | float | str) -> None:
        initial = round_money(to_decimal(initial_cash_mxn))
        if initial <= 0:
            raise ValueError("El efectivo inicial debe ser positivo.")
        self.initial_cash_mxn = initial
        self.cash_mxn = initial
        self.realized_pnl_mxn = Decimal("0.00")
        self.positions: dict[str, PaperPosition] = {}
        self.closed_positions: list[PaperPosition] = []
        self.orders: list[PaperOrder] = []
        self.trades: list[PaperTrade] = []
        self._ids = itertools.count(1)
        self._peak_equity = initial
        self._max_drawdown_pct = Decimal("0.0000")

    def open_position(
        self,
        *,
        book: str,
        price: Decimal,
        amount_mxn: Decimal,
        fee_rate: Decimal,
        signal_data: dict[str, Any] | None = None,
        stop_loss: Decimal | None = None,
        take_profit: Decimal | None = None,
        trailing_stop_pct: Decimal | None = None,
        expires_at: datetime | None = None,
    ) -> PaperPosition | None:
        amount = round_money(amount_mxn)
        entry_fee = round_money(amount * fee_rate)
        total_cost = amount + entry_fee
        order_id = self._next_id("ord")
        if total_cost > self.cash_mxn:
            self.orders.append(
                PaperOrder(
                    order_id,
                    book,
                    "buy",
                    "rejected",
                    amount,
                    price=price,
                    reason="Fondos insuficientes.",
                )
            )
            return None
        try:
            execution = BrokerSimulator(
                initial_capital_mxn=self.cash_mxn, fee_rate=fee_rate
            ).buy(
                opened_at=utc_now(),
                price=price,
                amount_mxn=amount,
                signal_data=signal_data or {},
            )
        except (InsufficientFundsError, ValueError) as exc:
            self.orders.append(
                PaperOrder(
                    order_id,
                    book,
                    "buy",
                    "rejected",
                    amount,
                    price=price,
                    reason=str(exc),
                )
            )
            return None
        self.cash_mxn = round_money(self.cash_mxn - total_cost)
        position = PaperPosition(
            id=self._next_id("pos"),
            book=book,
            quantity=execution.quantity,
            entry_price=execution.entry_price,
            amount_mxn=execution.amount_mxn,
            opened_at=execution.opened_at,
            entry_fee_mxn=execution.entry_fee_mxn,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop_pct=trailing_stop_pct,
            expires_at=expires_at,
            signal_data=signal_data or {},
        )
        if trailing_stop_pct is not None:
            position.trailing_stop_price = price * (
                Decimal("1") - trailing_stop_pct / Decimal("100")
            )
        self.positions[position.id] = position
        self.orders.append(
            PaperOrder(
                order_id, book, "buy", "filled", amount, execution.quantity, price
            )
        )
        return position

    def close_position(
        self, position_id: str, *, price: Decimal, fee_rate: Decimal, reason: str
    ) -> PaperTrade | None:
        position = self.positions.pop(position_id, None)
        if position is None:
            return None
        gross_exit = position.quantity * price
        exit_fee = round_money(gross_exit * fee_rate)
        cash_back = round_money(gross_exit - exit_fee)
        pnl = round_money(cash_back - position.amount_mxn - position.entry_fee_mxn)
        self.cash_mxn = round_money(self.cash_mxn + cash_back)
        self.realized_pnl_mxn = round_money(self.realized_pnl_mxn + pnl)
        position.status = "closed"
        position.closed_at = utc_now()
        position.exit_price = price
        position.exit_fee_mxn = exit_fee
        position.realized_pnl_mxn = pnl
        position.close_reason = reason
        self.closed_positions.append(position)
        trade = PaperTrade(
            id=self._next_id("trd"),
            position_id=position.id,
            book=position.book,
            opened_at=position.opened_at,
            closed_at=position.closed_at,
            entry_price=position.entry_price,
            exit_price=price,
            quantity=position.quantity,
            pnl_mxn=pnl,
            fees_mxn=round_money(position.entry_fee_mxn + exit_fee),
            reason=reason,
        )
        self.trades.append(trade)
        self.orders.append(
            PaperOrder(
                self._next_id("ord"),
                position.book,
                "sell",
                "filled",
                position.amount_mxn,
                position.quantity,
                price,
                reason=reason,
            )
        )
        return trade

    def update_market(
        self, prices: dict[str, Decimal], *, fee_rate: Decimal
    ) -> list[PaperTrade]:
        closed: list[PaperTrade] = []
        for position in list(self.positions.values()):
            price = prices.get(position.book)
            if price is None:
                continue
            reason = self._exit_reason(position, price)
            if reason is not None:
                trade = self.close_position(
                    position.id, price=price, fee_rate=fee_rate, reason=reason
                )
                if trade is not None:
                    closed.append(trade)
        self._record_drawdown(prices)
        return closed

    def manual_close(
        self, position_id: str, *, price: Decimal, fee_rate: Decimal
    ) -> PaperTrade | None:
        return self.close_position(
            position_id, price=price, fee_rate=fee_rate, reason="manual_close"
        )

    def snapshot(self, prices: dict[str, Decimal] | None = None) -> PortfolioSnapshot:
        prices = prices or {}
        unrealized = self.unrealized_pnl(prices)
        equity = self.equity(prices)
        self._record_drawdown(prices)
        return PortfolioSnapshot(
            cash_mxn=self.cash_mxn,
            equity_mxn=equity,
            realized_pnl_mxn=self.realized_pnl_mxn,
            unrealized_pnl_mxn=unrealized,
            max_drawdown_pct=self._max_drawdown_pct,
            open_positions=tuple(self.positions.values()),
            closed_positions=tuple(self.closed_positions),
            orders=tuple(self.orders),
            trades=tuple(self.trades),
        )

    def equity(self, prices: dict[str, Decimal] | None = None) -> Decimal:
        prices = prices or {}
        value = self.cash_mxn
        for position in self.positions.values():
            value += position.market_value(
                prices.get(position.book, position.entry_price)
            )
        return round_money(value)

    def unrealized_pnl(self, prices: dict[str, Decimal]) -> Decimal:
        return round_money(
            sum(
                (
                    position.unrealized_pnl(
                        prices.get(position.book, position.entry_price)
                    )
                    for position in self.positions.values()
                ),
                Decimal("0"),
            )
        )

    def exposure(
        self, book: str | None = None, prices: dict[str, Decimal] | None = None
    ) -> Decimal:
        prices = prices or {}
        total = Decimal("0")
        for position in self.positions.values():
            if book is None or position.book == book:
                total += position.market_value(
                    prices.get(position.book, position.entry_price)
                )
        return round_money(total)

    def _exit_reason(self, position: PaperPosition, price: Decimal) -> str | None:
        if position.expires_at is not None and utc_now() >= position.expires_at:
            return "expired"
        if position.trailing_stop_pct is not None:
            candidate = price * (
                Decimal("1") - position.trailing_stop_pct / Decimal("100")
            )
            if (
                position.trailing_stop_price is None
                or candidate > position.trailing_stop_price
            ):
                position.trailing_stop_price = candidate
            if (
                position.trailing_stop_price is not None
                and price <= position.trailing_stop_price
            ):
                return "trailing_stop"
        if position.stop_loss is not None and price <= position.stop_loss:
            return "stop_loss"
        if position.take_profit is not None and price >= position.take_profit:
            return "take_profit"
        return None

    def _record_drawdown(self, prices: dict[str, Decimal]) -> None:
        equity = self.equity(prices)
        if equity > self._peak_equity:
            self._peak_equity = equity
        if self._peak_equity > 0:
            drawdown = round_pct(
                ((self._peak_equity - equity) / self._peak_equity) * Decimal("100")
            )
            if drawdown > self._max_drawdown_pct:
                self._max_drawdown_pct = drawdown

    def _next_id(self, prefix: str) -> str:
        return f"{prefix}_{next(self._ids):06d}"
