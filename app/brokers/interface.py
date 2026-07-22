from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

BrokerMode = Literal["paper", "live"]
OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]


@dataclass(frozen=True)
class BrokerHealth:
    connected: bool
    mode: BrokerMode
    live_enabled: bool
    status: str
    errors: tuple[str, ...] = tuple()

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "mode": self.mode,
            "live_enabled": self.live_enabled,
            "status": self.status,
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class BrokerOrder:
    id: str
    book: str
    side: OrderSide
    type: OrderType
    status: str
    amount_mxn: Decimal
    price: Decimal | None = None
    created_at: datetime | None = None
    reason: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "book": self.book,
            "side": self.side,
            "type": self.type,
            "status": self.status,
            "amount_mxn": float(self.amount_mxn),
            "price": float(self.price) if self.price is not None else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class BrokerBalance:
    cash_mxn: Decimal
    equity_mxn: Decimal
    positions_value_mxn: Decimal = Decimal("0")
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "cash_mxn": float(self.cash_mxn),
            "equity_mxn": float(self.equity_mxn),
            "positions_value_mxn": float(self.positions_value_mxn),
            "metadata": self.metadata,
        }


class BrokerInterface(ABC):
    name: str
    mode: BrokerMode

    @abstractmethod
    def connect(self) -> BrokerHealth: ...

    @abstractmethod
    def disconnect(self) -> BrokerHealth: ...

    @abstractmethod
    def health(self) -> BrokerHealth: ...

    @abstractmethod
    def get_balance(self) -> BrokerBalance: ...

    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_orders(self) -> list[BrokerOrder]: ...

    @abstractmethod
    def place_market_buy(
        self, *, book: str, amount_mxn: Decimal, price: Decimal | None = None
    ) -> BrokerOrder: ...

    @abstractmethod
    def place_market_sell(
        self, *, book: str, amount_mxn: Decimal, price: Decimal | None = None
    ) -> BrokerOrder: ...

    @abstractmethod
    def place_limit_buy(
        self, *, book: str, amount_mxn: Decimal, price: Decimal
    ) -> BrokerOrder: ...

    @abstractmethod
    def place_limit_sell(
        self, *, book: str, amount_mxn: Decimal, price: Decimal
    ) -> BrokerOrder: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> BrokerOrder: ...

    @abstractmethod
    def get_order_status(self, order_id: str) -> BrokerOrder: ...

    @abstractmethod
    def get_ticker(self, book: str) -> dict[str, Any]: ...

    @abstractmethod
    def get_candles(
        self, book: str, timeframe: str, limit: int = 100
    ) -> list[dict[str, Any]]: ...
