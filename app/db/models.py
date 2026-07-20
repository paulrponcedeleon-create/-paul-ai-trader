from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SimulatedOrder(Base):
    __tablename__ = "simulated_orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    book: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    amount_mxn: Mapped[float] = mapped_column(Float, nullable=False)
    reference_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_pnl_mxn: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="simulated", index=True
    )
    strategy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    risk_check: Mapped[str] = mapped_column(String(255), nullable=False)

    def to_dict(self) -> dict[str, object]:
        asset_quantity = None
        if self.reference_price and self.reference_price > 0:
            asset_quantity = round(self.amount_mxn / self.reference_price, 12)

        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "status": self.status,
            "book": self.book,
            "side": self.side,
            "amount_mxn": round(self.amount_mxn, 2),
            "reference_price": self.reference_price,
            "asset_quantity": asset_quantity,
            "close_price": self.close_price,
            "realized_pnl_mxn": (
                round(self.realized_pnl_mxn, 2)
                if self.realized_pnl_mxn is not None
                else None
            ),
            "risk_check": self.risk_check,
        }
