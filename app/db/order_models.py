from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.services.money import public_money, public_price


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
    amount_mxn: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(30, 12), nullable=True)
    fee_mxn: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    realized_pnl_mxn: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
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
            "amount_mxn": public_money(self.amount_mxn),
            "price": public_price(self.price),
            "fee_mxn": public_money(self.fee_mxn),
            "realized_pnl_mxn": public_money(self.realized_pnl_mxn),
            "source": self.source,
            "reason": self.reason,
            "correlation_id": self.correlation_id,
        }
