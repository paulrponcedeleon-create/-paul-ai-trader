from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperAccount, PaperOrderRow, PaperPositionRow, PaperTradeRow


class PaperTradingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_account(
        self, *, account_id: str, cash_mxn: float, status: str
    ) -> dict[str, Any]:
        row = self.session.get(PaperAccount, account_id)
        if row is None:
            row = PaperAccount(
                id=account_id, cash_mxn=cash_mxn, equity_mxn=cash_mxn, status=status
            )
            self.session.add(row)
        else:
            row.cash_mxn = cash_mxn
            row.status = status
        self.session.flush()
        return {
            "id": row.id,
            "cash_mxn": row.cash_mxn,
            "equity_mxn": row.equity_mxn,
            "status": row.status,
        }

    def record_snapshot(self, account_id: str, snapshot: dict[str, Any]) -> None:
        row = self.session.get(PaperAccount, account_id)
        if row is not None:
            row.cash_mxn = float(snapshot["cash_mxn"])
            row.equity_mxn = float(snapshot["equity_mxn"])
            self.session.flush()

    def list_accounts(self) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(PaperAccount).order_by(PaperAccount.created_at.desc())
        ).all()
        return [
            {
                "id": row.id,
                "cash_mxn": row.cash_mxn,
                "equity_mxn": row.equity_mxn,
                "status": row.status,
            }
            for row in rows
        ]

    def list_positions(self, account_id: str) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(PaperPositionRow).where(PaperPositionRow.account_id == account_id)
        ).all()
        return [_row_dict(row) for row in rows]

    def list_orders(self, account_id: str) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(PaperOrderRow).where(PaperOrderRow.account_id == account_id)
        ).all()
        return [_row_dict(row) for row in rows]

    def list_trades(self, account_id: str) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(PaperTradeRow).where(PaperTradeRow.account_id == account_id)
        ).all()
        return [_row_dict(row) for row in rows]


def _row_dict(row: Any) -> dict[str, Any]:
    return {
        key: value for key, value in row.__dict__.items() if not key.startswith("_")
    }
