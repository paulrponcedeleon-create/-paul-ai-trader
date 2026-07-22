from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

MarketDataEventType = Literal[
    "ticker_updated", "candle_closed", "orderbook_updated", "reconnect", "disconnect"
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Ticker:
    book: str
    last: Decimal
    high: Decimal
    low: Decimal
    volume: Decimal
    vwap: Decimal
    timestamp: datetime = field(default_factory=utc_now)
    source: str = "unknown"

    @property
    def spread(self) -> Decimal:
        return max(self.high - self.low, Decimal("0"))

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self) | {"spread": float(self.spread)}


@dataclass(frozen=True)
class Candle:
    book: str
    timeframe: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    closed: bool = True

    @property
    def vwap(self) -> Decimal:
        return (self.high + self.low + self.close) / Decimal("3")

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self) | {"vwap": float(self.vwap)}


@dataclass(frozen=True)
class OrderBookLevel:
    price: Decimal
    amount: Decimal

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self)


@dataclass(frozen=True)
class OrderBook:
    book: str
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]
    timestamp: datetime = field(default_factory=utc_now)
    source: str = "unknown"

    @property
    def spread(self) -> Decimal:
        if not self.bids or not self.asks:
            return Decimal("0")
        return max(self.asks[0].price - self.bids[0].price, Decimal("0"))

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "book": self.book,
            "bids": [level.to_public_dict() for level in self.bids],
            "asks": [level.to_public_dict() for level in self.asks],
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "spread": float(self.spread),
        }


@dataclass(frozen=True)
class MarketTrade:
    book: str
    price: Decimal
    amount: Decimal
    side: str
    timestamp: datetime
    trade_id: str | None = None

    @property
    def notional(self) -> Decimal:
        return self.price * self.amount

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self) | {"notional": float(self.notional)}


@dataclass(frozen=True)
class MarketDataEvent:
    timestamp: datetime
    event_type: MarketDataEventType
    book: str | None
    source: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self)


@dataclass(frozen=True)
class ProviderStatus:
    provider: str
    connected: bool
    read_only: bool
    live_trading_enabled: bool
    subscriptions: tuple[str, ...]
    reconnects: int
    last_heartbeat_at: datetime | None
    last_error: str | None = None
    uptime_seconds: float = 0.0

    def to_public_dict(self) -> dict[str, Any]:
        return _public(self)


def D(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value if value.is_finite() else Decimal("0")
    try:
        parsed = Decimal(str(value))
    except Exception:
        return Decimal("0")
    return parsed if parsed.is_finite() else Decimal("0")


def _public(obj: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in obj.__dict__.items():
        if isinstance(value, Decimal):
            data[key] = float(value) if value.is_finite() else 0.0
        elif isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, tuple):
            data[key] = [
                item.to_public_dict() if hasattr(item, "to_public_dict") else item
                for item in value
            ]
        elif isinstance(value, dict):
            data[key] = value
        else:
            data[key] = value
    return data
