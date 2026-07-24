from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.services.money import public_money


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_reset_token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    password_reset_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    bot_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ai_exploration_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    shared_learning_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    simulated_initial_capital_mxn: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("5000.00")
    )
    bitso_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    bitso_api_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    bitso_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_public_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "email": self.email,
            "is_admin": self.is_admin,
            "is_active": self.is_active,
            "bot_enabled": self.bot_enabled,
            "ai_exploration_enabled": self.ai_exploration_enabled,
            "shared_learning_enabled": self.shared_learning_enabled,
            "simulated_initial_capital_mxn": public_money(
                self.simulated_initial_capital_mxn
            ),
            "bitso_connected": bool(
                self.bitso_api_key_encrypted and self.bitso_api_secret_encrypted
            ),
            "bitso_connected_at": (
                self.bitso_connected_at.isoformat() if self.bitso_connected_at else None
            ),
            "password_changed_at": (
                self.password_changed_at.isoformat() if self.password_changed_at else None
            ),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
