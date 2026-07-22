from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from app.market_data.cache import MarketDataCache
from app.market_data.models import (
    Candle,
    MarketDataEvent,
    MarketTrade,
    OrderBook,
    OrderBookLevel,
    ProviderStatus,
    Ticker,
    utc_now,
)
from app.market_data.provider import MarketDataProvider


class MockMarketDataProvider(MarketDataProvider):
    name = "mock"

    def __init__(self, cache: MarketDataCache | None = None) -> None:
        self.cache = cache or MarketDataCache()
        self.connected = False
        self.subscriptions: set[str] = set()
        self.reconnects = 0
        self.started_at = utc_now()
        self.last_heartbeat_at = None
        self.last_error = None

    async def connect(self) -> ProviderStatus:
        self.connected = True
        self.last_heartbeat_at = utc_now()
        self._event("reconnect", None, "mock provider connected")
        return self.status()

    async def disconnect(self) -> ProviderStatus:
        self.connected = False
        self._event("disconnect", None, "mock provider disconnected")
        return self.status()

    def status(self) -> ProviderStatus:
        uptime = (utc_now() - self.started_at).total_seconds()
        return ProviderStatus(
            self.name,
            self.connected,
            True,
            False,
            tuple(sorted(self.subscriptions)),
            self.reconnects,
            self.last_heartbeat_at,
            self.last_error,
            uptime,
        )

    async def subscribe(
        self, book: str, channels: tuple[str, ...] = ("ticker",)
    ) -> ProviderStatus:
        for channel in channels:
            self.subscriptions.add(f"{book}:{channel}")
        return self.status()

    async def heartbeat(self) -> ProviderStatus:
        if not self.connected:
            self.reconnects += 1
            await self.connect()
        self.last_heartbeat_at = utc_now()
        return self.status()

    async def reconnect(self) -> ProviderStatus:
        self.reconnects += 1
        self.connected = True
        self.last_heartbeat_at = utc_now()
        self._event("reconnect", None, "mock provider reconnected")
        return self.status()

    async def get_ticker(self, book: str) -> Ticker:
        base = Decimal("100") + Decimal(len(book))
        ticker = Ticker(
            book,
            base,
            base + Decimal("2"),
            base - Decimal("2"),
            Decimal("10"),
            base,
            source=self.name,
        )
        self.cache.update_ticker(ticker)
        self._event("ticker_updated", book, "ticker updated")
        return ticker

    async def get_candles(
        self, book: str, timeframe: str = "1m", limit: int = 100
    ) -> list[Candle]:
        now = utc_now().replace(microsecond=0)
        candles = []
        for idx in range(limit):
            price = Decimal("100") + Decimal(idx)
            candle = Candle(
                book,
                timeframe,
                now - timedelta(minutes=limit - idx),
                price,
                price + Decimal("1"),
                price - Decimal("1"),
                price + Decimal("0.5"),
                Decimal("10"),
            )
            candles.append(candle)
            self.cache.add_candle(candle)
        self._event("candle_closed", book, "candles updated", {"count": limit})
        return candles

    async def get_orderbook(self, book: str) -> OrderBook:
        orderbook = OrderBook(
            book,
            (OrderBookLevel(Decimal("99"), Decimal("1")),),
            (OrderBookLevel(Decimal("101"), Decimal("1.5")),),
            source=self.name,
        )
        self.cache.update_orderbook(orderbook)
        self._event("orderbook_updated", book, "orderbook updated")
        return orderbook

    async def get_recent_trades(self, book: str, limit: int = 100) -> list[MarketTrade]:
        now = utc_now()
        trades = [
            MarketTrade(
                book,
                Decimal("100") + Decimal(i),
                Decimal("0.1"),
                "buy" if i % 2 == 0 else "sell",
                now - timedelta(seconds=i),
                str(i),
            )
            for i in range(limit)
        ]
        for trade in trades:
            self.cache.add_trade(trade)
        return trades

    def _event(
        self,
        event_type: str,
        book: str | None,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        self.cache.add_event(
            MarketDataEvent(
                utc_now(), event_type, book, self.name, message, metadata or {}
            )
        )
