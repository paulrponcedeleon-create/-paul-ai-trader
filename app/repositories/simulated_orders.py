from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import SimulatedOrder
from app.services.money import (
    public_money,
    quantize_money,
    quantize_price,
    quantize_rate,
    to_decimal,
)


class SqlSimulatedOrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(SimulatedOrder)
            .order_by(SimulatedOrder.created_at.desc(), SimulatedOrder.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return [row.to_dict() for row in rows]

    def list_open(self) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(SimulatedOrder)
            .where(
                SimulatedOrder.status == "open",
                SimulatedOrder.reference_price.is_not(None),
            )
            .order_by(SimulatedOrder.created_at.desc(), SimulatedOrder.id.desc())
        ).all()
        return [row.to_dict() for row in rows]

    def list_closed(
        self,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        books: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        statement = select(SimulatedOrder).where(
            SimulatedOrder.status == "closed",
            SimulatedOrder.closed_at.is_not(None),
            SimulatedOrder.realized_pnl_mxn.is_not(None),
        )
        if start_at is not None:
            statement = statement.where(SimulatedOrder.closed_at >= start_at)
        if end_at is not None:
            statement = statement.where(SimulatedOrder.closed_at < end_at)
        if books:
            statement = statement.where(SimulatedOrder.book.in_(sorted(books)))

        rows = self.session.scalars(
            statement.order_by(SimulatedOrder.closed_at.asc(), SimulatedOrder.id.asc())
        ).all()
        return [row.to_dict() for row in rows]

    def capital_ledger_decimal(self, initial_capital_mxn: Any) -> dict[str, Decimal]:
        open_invested = self.session.scalar(
            select(
                func.coalesce(func.sum(SimulatedOrder.amount_mxn), Decimal("0.00"))
            ).where(SimulatedOrder.status == "open")
        )
        realized_pnl = self.session.scalar(
            select(
                func.coalesce(
                    func.sum(SimulatedOrder.realized_pnl_mxn), Decimal("0.00")
                )
            ).where(
                SimulatedOrder.status == "closed",
                SimulatedOrder.realized_pnl_mxn.is_not(None),
            )
        )
        initial = quantize_money(initial_capital_mxn)
        invested = quantize_money(open_invested or Decimal("0"))
        realized = quantize_money(realized_pnl or Decimal("0"))
        available = quantize_money(initial + realized - invested)
        equity_before_unrealized = quantize_money(initial + realized)
        return {
            "initial_capital_mxn": initial,
            "open_invested_mxn": invested,
            "realized_pnl_mxn": realized,
            "available_cash_mxn": max(Decimal("0.00"), available),
            "account_equity_before_unrealized_mxn": equity_before_unrealized,
        }

    def capital_ledger(self, initial_capital_mxn: Any) -> dict[str, float]:
        ledger = self.capital_ledger_decimal(initial_capital_mxn)
        return {key: float(public_money(value) or 0.0) for key, value in ledger.items()}

    def get_open(self, simulation_id: str) -> dict[str, Any] | None:
        row = self.session.get(SimulatedOrder, simulation_id)
        if row is None or row.status != "open" or row.reference_price is None:
            return None
        return row.to_dict()

    def count(self) -> int:
        total = self.session.scalar(select(func.count()).select_from(SimulatedOrder))
        return int(total or 0)

    def add(self, item: dict[str, Any]) -> dict[str, Any]:
        row = SimulatedOrder(
            id=str(item["id"]),
            created_at=item["created_at"],
            closed_at=item.get("closed_at"),
            status=str(item.get("status", "simulated")),
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
        if row is None or row.status != "open":
            return None

        row.status = "closed"
        row.closed_at = closed_at
        row.close_price = quantize_price(close_price)
        row.exit_fee_rate = quantize_rate(exit_fee_rate)
        row.exit_fee_mxn = quantize_money(exit_fee_mxn)
        row.realized_pnl_mxn = quantize_money(realized_pnl_mxn)
        self.session.flush()
        return row.to_dict()
