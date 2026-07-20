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

    def count(self) -> int:
        total = self.session.scalar(select(func.count()).select_from(SimulatedOrder))
        return int(total or 0)

    def add(self, item: dict[str, Any]) -> dict[str, Any]:
        row = SimulatedOrder(
            id=str(item["id"]),
            created_at=item["created_at"],
            status=str(item.get("status", "simulated")),
            book=str(item["book"]).lower(),
            side=str(item["side"]),
            amount_mxn=float(item["amount_mxn"]),
            reference_price=item.get("reference_price"),
            strategy_version=item.get("strategy_version"),
            signal_id=item.get("signal_id"),
            risk_decision_id=item.get("risk_decision_id"),
            correlation_id=item.get("correlation_id"),
            risk_check=str(item["risk_check"]),
        )
        self.session.add(row)
        self.session.flush()
        return row.to_dict()
