from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SimulatedOrder(Base):
    __tablename__ = "simulated_orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    book: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    amount_mxn: Mapped[float] = mapped_column(Float, nullable=False)
    reference_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="simulated")
    strategy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    risk_check: Mapped[str] = mapped_column(String(255), nullable=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "book": self.book,
            "side": self.side,
            "amount_mxn": round(self.amount_mxn, 2),
            "risk_check": self.risk_check,
        }
