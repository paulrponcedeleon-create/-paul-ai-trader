from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SimulatedOrderEvent(Base):
    __tablename__ = "simulated_order_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    position_id: Mapped[str | None] = mapped_column(
        String(40), nullable=True, index=True
    )
    book: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    amount_mxn: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    fee_mxn: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_pnl_mxn: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "position_id": self.position_id,
            "book": self.book,
            "side": self.side,
            "status": self.status,
            "amount_mxn": round(self.amount_mxn, 2),
            "price": self.price,
            "fee_mxn": round(self.fee_mxn, 2) if self.fee_mxn is not None else None,
            "realized_pnl_mxn": (
                round(self.realized_pnl_mxn, 2)
                if self.realized_pnl_mxn is not None
                else None
            ),
            "source": self.source,
            "reason": self.reason,
            "correlation_id": self.correlation_id,
        }
