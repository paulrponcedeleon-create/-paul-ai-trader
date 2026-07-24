from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import SimulatedOrder
from app.security.user_context import get_current_user_id
from app.services.money import public_money, quantize_money, quantize_price, quantize_rate
from app.services.trade_sources import infer_position_source, normalize_position_source


class SqlSimulatedOrderRepository:
    def __init__(self, session: Session, user_id: str | None = "current") -> None:
        self.session = session
        self.user_id = get_current_user_id() if user_id == "current" else user_id

    def _scope(self, statement):
        if self.user_id is not None:
            statement = statement.where(SimulatedOrder.user_id == self.user_id)
        return statement

    def list(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        statement = self._scope(select(SimulatedOrder))
        rows = self.session.scalars(
            statement.order_by(SimulatedOrder.created_at.desc(), SimulatedOrder.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return [row.to_dict() for row in rows]

    def list_open(self) -> list[dict[str, Any]]:
        statement = self._scope(
            select(SimulatedOrder).where(
                SimulatedOrder.status == "open",
                SimulatedOrder.reference_price.is_not(None),
            )
        )
        rows = self.session.scalars(
            statement.order_by(SimulatedOrder.created_at.desc(), SimulatedOrder.id.desc())
        ).all()
        return [row.to_dict() for row in rows]

    def list_closed(
        self,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        books: set[str] | None = None,
        sources: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        statement = self._scope(
            select(SimulatedOrder).where(
                SimulatedOrder.status == "closed",
                SimulatedOrder.closed_at.is_not(None),
                SimulatedOrder.realized_pnl_mxn.is_not(None),
            )
        )
        if start_at is not None:
            statement = statement.where(SimulatedOrder.closed_at >= start_at)
        if end_at is not None:
            statement = statement.where(SimulatedOrder.closed_at < end_at)
        if books:
            statement = statement.where(SimulatedOrder.book.in_(sorted(books)))
        if sources:
            normalized_sources = {normalize_position_source(source) for source in sources}
            statement = statement.where(SimulatedOrder.source.in_(sorted(normalized_sources)))
        rows = self.session.scalars(
            statement.order_by(SimulatedOrder.closed_at.asc(), SimulatedOrder.id.asc())
        ).all()
        return [row.to_dict() for row in rows]

    def capital_ledger_decimal(self, initial_capital_mxn: Any) -> dict[str, Decimal]:
        open_statement = self._scope(
            select(func.coalesce(func.sum(SimulatedOrder.amount_mxn), Decimal("0.00"))).where(
                SimulatedOrder.status == "open"
            )
        )
        pnl_statement = self._scope(
            select(
                func.coalesce(func.sum(SimulatedOrder.realized_pnl_mxn), Decimal("0.00"))
            ).where(
                SimulatedOrder.status == "closed",
                SimulatedOrder.realized_pnl_mxn.is_not(None),
            )
        )
        open_invested = self.session.scalar(open_statement)
        realized_pnl = self.session.scalar(pnl_statement)
        initial = quantize_money(initial_capital_mxn)
        invested = quantize_money(open_invested or Decimal("0"))
        realized = quantize_money(realized_pnl or Decimal("0"))
        available = quantize_money(initial + realized - invested)
        return {
            "initial_capital_mxn": initial,
            "open_invested_mxn": invested,
            "realized_pnl_mxn": realized,
            "available_cash_mxn": max(Decimal("0.00"), available),
            "account_equity_before_unrealized_mxn": quantize_money(initial + realized),
        }

    def capital_ledger(self, initial_capital_mxn: Any) -> dict[str, float]:
        ledger = self.capital_ledger_decimal(initial_capital_mxn)
        return {key: float(public_money(value) or 0.0) for key, value in ledger.items()}

    def get_open(self, simulation_id: str) -> dict[str, Any] | None:
        row = self.session.get(SimulatedOrder, simulation_id)
        if (
            row is None
            or row.status != "open"
            or row.reference_price is None
            or (self.user_id is not None and row.user_id != self.user_id)
        ):
            return None
        return row.to_dict()

    def count(self) -> int:
        statement = self._scope(select(func.count()).select_from(SimulatedOrder))
        return int(self.session.scalar(statement) or 0)

    def add(self, item: dict[str, Any]) -> dict[str, Any]:
        source = infer_position_source(item)
        resolved_user_id = str(item.get("user_id") or self.user_id or "owner")
        row = SimulatedOrder(
            id=str(item["id"]),
            user_id=resolved_user_id,
            created_at=item["created_at"],
            closed_at=item.get("closed_at"),
            parent_position_id=item.get("parent_position_id"),
            status=str(item.get("status", "simulated")),
            source=source,
            book=str(item["book"]).lower(),
            side=str(item["side"]),
            amount_mxn=quantize_money(item["amount_mxn"]),
            reference_price=(
                quantize_price(item["reference_price"])
                if item.get("reference_price") is not None
                else None
            ),
            close_price=(
                quantize_price(item["close_price"])
                if item.get("close_price") is not None
                else None
            ),
            entry_fee_rate=(
                quantize_rate(item["entry_fee_rate"])
                if item.get("entry_fee_rate") is not None
                else None
            ),
            entry_fee_mxn=(
                quantize_money(item["entry_fee_mxn"])
                if item.get("entry_fee_mxn") is not None
                else None
            ),
            exit_fee_rate=(
                quantize_rate(item["exit_fee_rate"])
                if item.get("exit_fee_rate") is not None
                else None
            ),
            exit_fee_mxn=(
                quantize_money(item["exit_fee_mxn"])
                if item.get("exit_fee_mxn") is not None
                else None
            ),
            realized_pnl_mxn=(
                quantize_money(item["realized_pnl_mxn"])
                if item.get("realized_pnl_mxn") is not None
                else None
            ),
            strategy_version=item.get("strategy_version"),
            signal_id=item.get("signal_id"),
            risk_decision_id=item.get("risk_decision_id"),
            correlation_id=item.get("correlation_id"),
            risk_check=str(item["risk_check"]),
        )
        self.session.add(row)
        self.session.flush()
        return row.to_dict()

    def close(
        self,
        simulation_id: str,
        *,
        closed_at: datetime,
        close_price: Any,
        exit_fee_rate: Any,
        exit_fee_mxn: Any,
        realized_pnl_mxn: Any,
    ) -> dict[str, Any] | None:
        row = self.session.get(SimulatedOrder, simulation_id)
        if row is None or row.status != "open" or (
            self.user_id is not None and row.user_id != self.user_id
        ):
            return None
        row.status = "closed"
        row.closed_at = closed_at
        row.close_price = quantize_price(close_price)
        row.exit_fee_rate = quantize_rate(exit_fee_rate)
        row.exit_fee_mxn = quantize_money(exit_fee_mxn)
        row.realized_pnl_mxn = quantize_money(realized_pnl_mxn)
        self.session.flush()
        return row.to_dict()

    def close_partial(
        self,
        simulation_id: str,
        *,
        closed_lot_id: str,
        amount_mxn: Any,
        closed_at: datetime,
        close_price: Any,
        exit_fee_rate: Any,
        exit_fee_mxn: Any,
        realized_pnl_mxn: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        row = self.session.get(SimulatedOrder, simulation_id)
        if row is None or row.status != "open" or (
            self.user_id is not None and row.user_id != self.user_id
        ):
            return None
        amount = quantize_money(amount_mxn)
        if amount <= Decimal("0.00") or amount >= row.amount_mxn:
            raise ValueError("El cierre parcial debe ser menor que el monto abierto.")

        original_amount = row.amount_mxn
        ratio = amount / original_amount
        original_entry_fee = row.entry_fee_mxn or Decimal("0.00")
        sold_entry_fee = quantize_money(original_entry_fee * ratio)
        remaining_entry_fee = quantize_money(original_entry_fee - sold_entry_fee)

        closed_row = SimulatedOrder(
            id=closed_lot_id,
            user_id=row.user_id,
            created_at=row.created_at,
            closed_at=closed_at,
            parent_position_id=row.parent_position_id or row.id,
            status="closed",
            source=row.source,
            book=row.book,
            side=row.side,
            amount_mxn=amount,
            reference_price=row.reference_price,
            close_price=quantize_price(close_price),
            entry_fee_rate=row.entry_fee_rate,
            entry_fee_mxn=sold_entry_fee,
            exit_fee_rate=quantize_rate(exit_fee_rate),
            exit_fee_mxn=quantize_money(exit_fee_mxn),
            realized_pnl_mxn=quantize_money(realized_pnl_mxn),
            strategy_version=row.strategy_version,
            signal_id=row.signal_id,
            risk_decision_id=row.risk_decision_id,
            correlation_id=row.correlation_id,
            risk_check=row.risk_check,
        )
        row.amount_mxn = quantize_money(original_amount - amount)
        row.entry_fee_mxn = remaining_entry_fee
        self.session.add(closed_row)
        self.session.flush()
        return closed_row.to_dict(), row.to_dict()
