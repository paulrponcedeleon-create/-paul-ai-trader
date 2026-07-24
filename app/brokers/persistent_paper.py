from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import secrets
from typing import Any, Callable

from app.brokers.interface import BrokerBalance, BrokerOrder
from app.brokers.paper import PaperBroker
from app.paper_trading import PaperTradingEngine, PortfolioManager
from app.paper_trading.models import PaperPosition, PaperTrade
from app.repositories.order_events import SqlSimulatedOrderEventRepository
from app.repositories.simulated_orders import SqlSimulatedOrderRepository
from app.services.money import public_money, quantize_money, to_decimal


class PersistentPortfolioManager(PortfolioManager):
    """Paper portfolio with process-independent identifiers."""

    def _next_id(self, prefix: str) -> str:
        return f"{prefix}_{secrets.token_hex(6)}"


class PersistentPaperBroker(PaperBroker):
    """Paper broker backed by the same PostgreSQL rows used by the dashboard.

    PostgreSQL is the authority for open positions, available simulated cash, and
    realized P&L. The in-memory portfolio remains the execution model for a
    running process and is reconciled from the database before every operation.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any],
        settings: Any,
    ) -> None:
        initial_cash = quantize_money(
            getattr(settings, "simulated_initial_capital_mxn", 1000)
        )
        portfolio = PersistentPortfolioManager(initial_cash_mxn=initial_cash)
        super().__init__(
            engine=PaperTradingEngine(portfolio=portfolio),
            settings=settings,
        )
        self.session_factory = session_factory
        self.settings = settings
        self.initial_cash_mxn = initial_cash
        self._sync_from_database()

    def get_balance(self) -> BrokerBalance:
        ledger, closed_count = self._sync_from_database()
        positions_value = sum(
            (
                position.market_value(
                    self._last_prices.get(position.book, position.entry_price)
                )
                for position in self.engine.portfolio.positions.values()
            ),
            Decimal("0"),
        )
        cash = ledger["available_cash_mxn"]
        realized = ledger["realized_pnl_mxn"]
        invested = ledger["open_invested_mxn"]
        equity = quantize_money(cash + positions_value)
        unrealized = quantize_money(positions_value - invested)
        return BrokerBalance(
            cash,
            equity,
            quantize_money(positions_value),
            {
                "broker": self.name,
                "persistent": True,
                "realized_pnl_mxn": public_money(realized),
                "unrealized_pnl_mxn": public_money(unrealized),
                "closed_trades": closed_count,
            },
        )

    def get_positions(self) -> list[dict[str, Any]]:
        self._sync_from_database()
        return super().get_positions()

    def get_exploration_metrics(self) -> dict[str, Any]:
        """Return persisted exploration counters without mixing strategy metrics."""
        with self.session_factory() as session:
            event_repository = SqlSimulatedOrderEventRepository(session)
            order_repository = SqlSimulatedOrderRepository(session)
            entries = event_repository.count(source="exploration", side="buy")
            exits = event_repository.count(source="exploration", side="sell")
            latest = event_repository.list(limit=1, source="exploration")
            active = sum(
                1
                for row in order_repository.list_open()
                if str(row.get("risk_check") or "").startswith("paper_exploration_")
            )
        return {
            "entries": entries,
            "exits": exits,
            "events": entries + exits,
            "active_positions": active,
            "last_experience": latest[0] if latest else None,
            "persistent": True,
        }

    def place_market_buy(
        self, *, book: str, amount_mxn: Decimal, price: Decimal | None = None
    ) -> BrokerOrder:
        self._sync_from_database()
        before = set(self.engine.portfolio.positions)
        result = super().place_market_buy(
            book=book,
            amount_mxn=amount_mxn,
            price=price,
        )
        if result.status != "filled":
            return result

        created_ids = set(self.engine.portfolio.positions) - before
        if not created_ids:
            return result
        position = self.engine.portfolio.positions[next(iter(created_ids))]
        self._persist_open_position(position, correlation_id=result.id)
        return BrokerOrder(
            position.id,
            result.book,
            result.side,
            result.type,
            result.status,
            result.amount_mxn,
            result.price,
            result.created_at,
            result.reason,
        )

    def place_market_sell(
        self, *, book: str, amount_mxn: Decimal, price: Decimal | None = None
    ) -> BrokerOrder:
        self._require_connected()
        source, reason = self._consume_execution_context("strategy_sell")
        self._sync_from_database()
        execution_price = price or self._last_prices.get(book) or Decimal("1")
        self._last_prices[book] = execution_price
        position = next(
            (
                item
                for item in self.engine.portfolio.positions.values()
                if item.book == book
            ),
            None,
        )
        if position is None:
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

        closed_amount = position.amount_mxn
        trade = self.engine.portfolio.close_position(
            position.id,
            price=execution_price,
            fee_rate=Decimal("0"),
            reason=reason,
        )
        if trade is None:
            return BrokerOrder(
                "paper_close_rejected",
                book,
                "sell",
                "market",
                "rejected",
                closed_amount,
                execution_price,
                reason="No fue posible cerrar la posición simulada.",
            )
        self._persist_closed_trade(trade, source=source)
        order = self.engine.portfolio.orders[-1]
        return BrokerOrder(
            order.id,
            book,
            "sell",
            "market",
            "filled",
            closed_amount,
            execution_price,
            order.created_at,
            reason,
        )

    def update_market(self, book: str, price: Decimal) -> list[PaperTrade]:
        self._sync_from_database()
        closed = super().update_market(book, price)
        for trade in closed:
            self._persist_closed_trade(trade, source="automatic_exit")
        return closed

    def _sync_from_database(self) -> tuple[dict[str, Decimal], int]:
        with self.session_factory() as session:
            repository = SqlSimulatedOrderRepository(session)
            open_rows = repository.list_open()
            closed_rows = repository.list_closed()
            ledger = repository.capital_ledger_decimal(self.initial_cash_mxn)

        open_ids = {str(row["id"]) for row in open_rows}
        for position_id in list(self.engine.portfolio.positions):
            if position_id not in open_ids:
                self.engine.portfolio.positions.pop(position_id, None)

        for row in open_rows:
            position_id = str(row["id"])
            if position_id in self.engine.portfolio.positions:
                continue
            position = self._position_from_row(row)
            self.engine.portfolio.positions[position.id] = position

        self.engine.portfolio.cash_mxn = ledger["available_cash_mxn"]
        self.engine.portfolio.realized_pnl_mxn = ledger["realized_pnl_mxn"]
        return ledger, len(closed_rows)

    def _position_from_row(self, row: dict[str, Any]) -> PaperPosition:
        entry_price = to_decimal(row["reference_price"])
        amount = to_decimal(row["amount_mxn"])
        quantity_value = row.get("asset_quantity")
        quantity = (
            to_decimal(quantity_value)
            if quantity_value is not None
            else amount / entry_price
        )
        opened_at = self._parse_datetime(row["created_at"])
        stop_loss = entry_price * (
            Decimal("1") - self.stop_loss_pct / Decimal("100")
        )
        take_profit = entry_price * (
            Decimal("1") + self.take_profit_pct / Decimal("100")
        )
        trailing_stop_price = entry_price * (
            Decimal("1") - self.trailing_stop_pct / Decimal("100")
        )
        risk_check = str(row.get("risk_check") or "runtime_paper_fill")
        source = (
            "exploration"
            if risk_check.startswith("paper_exploration_")
            else "runtime"
        )
        return PaperPosition(
            id=str(row["id"]),
            book=str(row["book"]),
            quantity=quantity,
            entry_price=entry_price,
            amount_mxn=amount,
            opened_at=opened_at,
            entry_fee_mxn=to_decimal(row.get("entry_fee_mxn") or 0),
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop_pct=self.trailing_stop_pct,
            trailing_stop_price=trailing_stop_price,
            signal_data={
                "broker": self.name,
                "source": source,
                "reason": risk_check,
                "risk_check": risk_check,
            },
        )

    def _persist_open_position(
        self, position: PaperPosition, *, correlation_id: str
    ) -> None:
        signal_data = position.signal_data or {}
        source = str(signal_data.get("source") or "runtime").lower()
        reason = str(signal_data.get("reason") or "strategy_buy")
        with self.session_factory() as session:
            repository = SqlSimulatedOrderRepository(session)
            event_repository = SqlSimulatedOrderEventRepository(session)
            repository.add(
                {
                    "id": position.id,
                    "created_at": position.opened_at,
                    "status": "open",
                    "book": position.book,
                    "side": "buy",
                    "amount_mxn": position.amount_mxn,
                    "reference_price": position.entry_price,
                    "entry_fee_rate": Decimal("0"),
                    "entry_fee_mxn": position.entry_fee_mxn,
                    "correlation_id": correlation_id,
                    "risk_check": reason,
                }
            )
            event_repository.add(
                {
                    "id": f"evt_{secrets.token_hex(8)}",
                    "created_at": position.opened_at,
                    "position_id": position.id,
                    "book": position.book,
                    "side": "buy",
                    "status": "filled",
                    "amount_mxn": position.amount_mxn,
                    "price": position.entry_price,
                    "fee_mxn": position.entry_fee_mxn,
                    "source": source,
                    "reason": reason,
                    "correlation_id": correlation_id,
                }
            )
            session.commit()

    def _persist_closed_trade(
        self, trade: PaperTrade, *, source: str | None = None
    ) -> None:
        closed_position = next(
            (
                position
                for position in reversed(self.engine.portfolio.closed_positions)
                if position.id == trade.position_id
                and position.closed_at == trade.closed_at
            ),
            None,
        )
        exit_fee = (
            closed_position.exit_fee_mxn
            if closed_position is not None
            else Decimal("0")
        )
        closed_amount = (
            closed_position.amount_mxn
            if closed_position is not None
            else trade.quantity * trade.entry_price
        )
        resolved_source = source
        if resolved_source is None:
            resolved_source = (
                "exploration"
                if str(trade.reason).startswith("paper_exploration_")
                else "runtime"
                if trade.reason == "strategy_sell"
                else "automatic_exit"
            )
        with self.session_factory() as session:
            repository = SqlSimulatedOrderRepository(session)
            event_repository = SqlSimulatedOrderEventRepository(session)
            repository.close(
                trade.position_id,
                closed_at=trade.closed_at,
                close_price=trade.exit_price,
                exit_fee_rate=Decimal("0"),
                exit_fee_mxn=exit_fee,
                realized_pnl_mxn=trade.pnl_mxn,
            )
            event_repository.add(
                {
                    "id": f"evt_{secrets.token_hex(8)}",
                    "created_at": trade.closed_at,
                    "position_id": trade.position_id,
                    "book": trade.book,
                    "side": "sell",
                    "status": "filled",
                    "amount_mxn": closed_amount,
                    "price": trade.exit_price,
                    "fee_mxn": exit_fee,
                    "realized_pnl_mxn": trade.pnl_mxn,
                    "source": resolved_source,
                    "reason": trade.reason,
                    "correlation_id": trade.id,
                }
            )
            session.commit()

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))
