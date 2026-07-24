from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.order_models import SimulatedOrderEvent
from app.security.user_context import get_current_user_id
from app.services.money import quantize_money, quantize_price


class SqlSimulatedOrderEventRepository:
    def __init__(self, session: Session, user_id: str | None = "current") -> None:
        self.session = session
        self.user_id = get_current_user_id() if user_id == "current" else user_id

    def _scope(self, statement):
        if self.user_id is not None:
            statement = statement.where(SimulatedOrderEvent.user_id == self.user_id)
        return statement

    def list(
        self,
        *,
        limit: int = 10,
        offset: int = 0,
        books: set[str] | None = None,
        side: str | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        statement = self._scope(select(SimulatedOrderEvent))
        if books:
            statement = statement.where(
                SimulatedOrderEvent.book.in_(sorted(book.lower() for book in books))
            )
        if side:
            statement = statement.where(SimulatedOrderEvent.side == side.lower())
        if source:
            statement = statement.where(SimulatedOrderEvent.source == source.lower())
        rows = self.session.scalars(
            statement.order_by(
                SimulatedOrderEvent.created_at.desc(), SimulatedOrderEvent.id.desc()
            )
            .limit(limit)
            .offset(offset)
        ).all()
        return [row.to_dict() for row in rows]

    def count(
        self,
        *,
        books: set[str] | None = None,
        side: str | None = None,
        source: str | None = None,
    ) -> int:
        statement = self._scope(select(func.count()).select_from(SimulatedOrderEvent))
        if books:
            statement = statement.where(
                SimulatedOrderEvent.book.in_(sorted(book.lower() for book in books))
            )
        if side:
            statement = statement.where(SimulatedOrderEvent.side == side.lower())
        if source:
            statement = statement.where(SimulatedOrderEvent.source == source.lower())
        return int(self.session.scalar(statement) or 0)

    def add(self, item: dict[str, Any]) -> dict[str, Any]:
        row = SimulatedOrderEvent(
            id=str(item["id"]),
            user_id=str(item.get("user_id") or self.user_id or "owner"),
            created_at=item["created_at"],
            position_id=(
                str(item["position_id"]) if item.get("position_id") is not None else None
            ),
            book=str(item["book"]).lower(),
            side=str(item["side"]).lower(),
            status=str(item.get("status", "filled")).lower(),
            amount_mxn=quantize_money(item["amount_mxn"]),
            price=(
                quantize_price(item["price"])
                if item.get("price") is not None
                else None
            ),
            fee_mxn=(
                quantize_money(item["fee_mxn"])
                if item.get("fee_mxn") is not None
                else None
            ),
            realized_pnl_mxn=(
                quantize_money(item["realized_pnl_mxn"])
                if item.get("realized_pnl_mxn") is not None
                else None
            ),
            source=str(item.get("source", "manual")).lower(),
            reason=str(item["reason"]) if item.get("reason") is not None else None,
            correlation_id=(
                str(item["correlation_id"])
                if item.get("correlation_id") is not None
                else None
            ),
        )
        self.session.add(row)
        self.session.flush()
        return row.to_dict()
