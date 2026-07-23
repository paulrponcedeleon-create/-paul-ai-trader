from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.brokers.interface import (
    BrokerBalance,
    BrokerHealth,
    BrokerInterface,
    BrokerOrder,
)
from app.paper_trading import PaperTradingEngine, PortfolioManager
from app.services.backtest_metrics import to_decimal


class PaperBroker(BrokerInterface):
    name = "paper"
    mode = "paper"

    def __init__(
        self,
        *,
        engine: PaperTradingEngine | None = None,
        initial_cash_mxn: Decimal | int | float | str | None = None,
        settings: Any | None = None,
    ) -> None:
        configured_cash = initial_cash_mxn
        if configured_cash is None:
            configured_cash = getattr(settings, "simulated_initial_capital_mxn", 1000)
        self.engine = engine or PaperTradingEngine(
            portfolio=PortfolioManager(initial_cash_mxn=configured_cash)
        )
        self.connected = False
        self._last_prices: dict[str, Decimal] = {}
        self.stop_loss_pct = to_decimal(getattr(settings, "paper_stop_loss_pct", 3.0))
        self.take_profit_pct = to_decimal(
            getattr(settings, "paper_take_profit_pct", 6.0)
        )
        self.trailing_stop_pct = to_decimal(
            getattr(settings, "paper_trailing_stop_pct", 2.0)
        )

    def connect(self) -> BrokerHealth:
        self.connected = True
        return self.health()

    def disconnect(self) -> BrokerHealth:
        self.connected = False
        return self.health()

    def health(self) -> BrokerHealth:
        return BrokerHealth(
            self.connected,
            "paper",
            False,
            "simulation" if self.connected else "disconnected",
            tuple(),
        )

    def get_balance(self) -> BrokerBalance:
        snapshot = self.engine.portfolio.snapshot(self._last_prices)
        positions_value = snapshot.equity_mxn - snapshot.cash_mxn
        return BrokerBalance(
            snapshot.cash_mxn,
            snapshot.equity_mxn,
            positions_value,
            {
                "broker": self.name,
                "realized_pnl_mxn": float(snapshot.realized_pnl_mxn),
                "unrealized_pnl_mxn": float(snapshot.unrealized_pnl_mxn),
                "closed_trades": len(snapshot.trades),
            },
        )

    def get_positions(self) -> list[dict[str, Any]]:
        return [
            position.__dict__ for position in self.engine.portfolio.positions.values()
        ]

    def get_orders(self) -> list[BrokerOrder]:
        return [
            BrokerOrder(
                order.id,
                order.book,
                order.side,
                "market",
                order.status,
                order.requested_amount_mxn,
                order.price,
                order.created_at,
                order.reason,
            )
            for order in self.engine.portfolio.orders
        ]

    def update_market(self, book: str, price: Decimal) -> list[Any]:
        self._last_prices[book] = price
        return self.engine.portfolio.update_market({book: price}, fee_rate=Decimal("0"))

    def place_market_buy(
        self, *, book: str, amount_mxn: Decimal, price: Decimal | None = None
    ) -> BrokerOrder:
        self._require_connected()
        execution_price = price or self._last_prices.get(book) or Decimal("1")
        self._last_prices[book] = execution_price
        before = len(self.engine.portfolio.orders)
        stop_loss = execution_price * (
            Decimal("1") - self.stop_loss_pct / Decimal("100")
        )
        take_profit = execution_price * (
            Decimal("1") + self.take_profit_pct / Decimal("100")
        )
        position = self.engine.portfolio.open_position(
            book=book,
            price=execution_price,
            amount_mxn=to_decimal(amount_mxn),
            fee_rate=Decimal("0"),
            signal_data={"broker": self.name},
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop_pct=self.trailing_stop_pct,
        )
        order = (
            self.engine.portfolio.orders[-1]
            if len(self.engine.portfolio.orders) > before
            else None
        )
        status = "filled" if position is not None else "rejected"
        return BrokerOrder(
            order.id if order else "paper_rejected",
            book,
            "buy",
            "market",
            status,
            to_decimal(amount_mxn),
            execution_price,
            order.created_at if order else None,
            order.reason if order else None,
        )

    def place_market_sell(
        self, *, book: str, amount_mxn: Decimal, price: Decimal | None = None
    ) -> BrokerOrder:
        self._require_connected()
        execution_price = price or self._last_prices.get(book) or Decimal("1")
        for position in list(self.engine.portfolio.positions.values()):
            if position.book == book:
                self.engine.portfolio.close_position(
                    position.id,
                    price=execution_price,
                    fee_rate=Decimal("0"),
                    reason="strategy_sell",
                    amount_mxn=amount_mxn,
                )
                order = self.engine.portfolio.orders[-1]
                return BrokerOrder(
                    order.id,
                    book,
                    "sell",
                    "market",
                    "filled",
                    to_decimal(amount_mxn),
                    execution_price,
                    order.created_at,
                    order.reason,
                )
        return BrokerOrder(
            "paper_no_position",
            book,
            "sell",
            "market",
            "rejected",
            to_decimal(amount_mxn),
            execution_price,
            reason="Sin posición abierta.",
        )

    def place_limit_buy(
        self, *, book: str, amount_mxn: Decimal, price: Decimal
    ) -> BrokerOrder:
        return self.place_market_buy(book=book, amount_mxn=amount_mxn, price=price)

    def place_limit_sell(
        self, *, book: str, amount_mxn: Decimal, price: Decimal
    ) -> BrokerOrder:
        return self.place_market_sell(book=book, amount_mxn=amount_mxn, price=price)

    def cancel_order(self, order_id: str) -> BrokerOrder:
        for order in self.get_orders():
            if order.id == order_id:
                return BrokerOrder(
                    order.id,
                    order.book,
                    order.side,
                    order.type,
                    "cancelled",
                    order.amount_mxn,
                    order.price,
                    order.created_at,
                    "cancelled",
                )
        return BrokerOrder(
            order_id,
            "unknown",
            "buy",
            "market",
            "cancelled",
            Decimal("0"),
            reason="Orden no encontrada; cancelación idempotente.",
        )

    def get_order_status(self, order_id: str) -> BrokerOrder:
        for order in self.get_orders():
            if order.id == order_id:
                return order
        return BrokerOrder(
            order_id,
            "unknown",
            "buy",
            "market",
            "rejected",
            Decimal("0"),
            reason="Orden no encontrada.",
        )

    def get_ticker(self, book: str) -> dict[str, Any]:
        return {
            "book": book,
            "last": float(self._last_prices.get(book, Decimal("1"))),
            "source": "paper",
        }

    def get_candles(
        self, book: str, timeframe: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        return []

    def _require_connected(self) -> None:
        if not self.connected:
            raise RuntimeError("Broker paper desconectado.")
