from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

PositionStatus = Literal["open", "closed"]
OrderStatus = Literal["accepted", "rejected", "filled", "expired", "cancelled"]
SizingMethod = Literal["fixed_size", "fixed_fractional", "percentage_of_equity"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class PaperTradingRequest:
    account_id: str
    book: str
    strategy_name: str
    strategy_version: str = "1.0"
    parameters: dict[str, Any] = field(default_factory=dict)
    fee_rate: Decimal | int | float | str = Decimal("0.001")
    sizing_method: SizingMethod = "fixed_size"
    sizing_value: Decimal | int | float | str = Decimal("1000")


@dataclass
class PaperPosition:
    id: str
    book: str
    quantity: Decimal
    entry_price: Decimal
    amount_mxn: Decimal
    opened_at: datetime
    entry_fee_mxn: Decimal = Decimal("0.00")
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    trailing_stop_pct: Decimal | None = None
    trailing_stop_price: Decimal | None = None
    expires_at: datetime | None = None
    signal_data: dict[str, Any] = field(default_factory=dict)
    status: PositionStatus = "open"
    closed_at: datetime | None = None
    exit_price: Decimal | None = None
    exit_fee_mxn: Decimal = Decimal("0.00")
    realized_pnl_mxn: Decimal = Decimal("0.00")
    close_reason: str | None = None

    def market_value(self, price: Decimal) -> Decimal:
        return self.quantity * price

    def unrealized_pnl(self, price: Decimal) -> Decimal:
        return self.market_value(price) - self.amount_mxn - self.entry_fee_mxn

    def closed_copy(
        self,
        *,
        quantity: Decimal,
        amount_mxn: Decimal,
        entry_fee_mxn: Decimal,
        closed_at: datetime,
        exit_price: Decimal,
        exit_fee_mxn: Decimal,
        realized_pnl_mxn: Decimal,
        close_reason: str,
    ) -> PaperPosition:
        return PaperPosition(
            id=self.id,
            book=self.book,
            quantity=quantity,
            entry_price=self.entry_price,
            amount_mxn=amount_mxn,
            opened_at=self.opened_at,
            entry_fee_mxn=entry_fee_mxn,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            trailing_stop_pct=self.trailing_stop_pct,
            trailing_stop_price=self.trailing_stop_price,
            expires_at=self.expires_at,
            signal_data=dict(self.signal_data),
            status="closed",
            closed_at=closed_at,
            exit_price=exit_price,
            exit_fee_mxn=exit_fee_mxn,
            realized_pnl_mxn=realized_pnl_mxn,
            close_reason=close_reason,
        )


@dataclass(frozen=True)
class PaperOrder:
    id: str
    book: str
    side: Literal["buy", "sell"]
    status: OrderStatus
    requested_amount_mxn: Decimal
    filled_quantity: Decimal = Decimal("0")
    price: Decimal | None = None
    created_at: datetime = field(default_factory=utc_now)
    reason: str | None = None


@dataclass(frozen=True)
class PaperTrade:
    id: str
    position_id: str
    book: str
    opened_at: datetime
    closed_at: datetime
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    pnl_mxn: Decimal
    fees_mxn: Decimal
    reason: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "position_id": self.position_id,
            "book": self.book,
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat(),
            "entry_price": float(self.entry_price),
            "exit_price": float(self.exit_price),
            "quantity": float(self.quantity),
            "pnl_mxn": float(self.pnl_mxn),
            "fees_mxn": float(self.fees_mxn),
            "reason": self.reason,
        }
