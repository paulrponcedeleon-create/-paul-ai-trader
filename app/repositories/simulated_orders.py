from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import SimulatedOrder


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
            amount_mxn=float(item["amount_mxn"]),
            reference_price=item.get("reference_price"),
            close_price=item.get("close_price"),
            entry_fee_rate=item.get("entry_fee_rate"),
            entry_fee_mxn=item.get("entry_fee_mxn"),
            exit_fee_rate=item.get("exit_fee_rate"),
            exit_fee_mxn=item.get("exit_fee_mxn"),
            realized_pnl_mxn=item.get("realized_pnl_mxn"),
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
        close_price: float,
        exit_fee_rate: float,
        exit_fee_mxn: float,
        realized_pnl_mxn: float,
    ) -> dict[str, Any] | None:
        row = self.session.get(SimulatedOrder, simulation_id)
        if row is None or row.status != "open":
            return None

        row.status = "closed"
        row.closed_at = closed_at
        row.close_price = float(close_price)
        row.exit_fee_rate = float(exit_fee_rate)
        row.exit_fee_mxn = float(exit_fee_mxn)
        row.realized_pnl_mxn = float(realized_pnl_mxn)
        self.session.flush()
        return row.to_dict()
