from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from app.market_data.cache import MarketDataCache
from app.market_data.mock import MockMarketDataProvider
from app.market_data.models import (
    Candle,
    D,
    MarketTrade,
    OrderBook,
    OrderBookLevel,
    ProviderStatus,
    Ticker,
    utc_now,
)
from app.services.bitso import BitsoClient


class BitsoMarketDataProvider(MockMarketDataProvider):
    """Read-only Bitso public-data provider.

    This provider never sends orders, never signs private requests, and degrades to
    deterministic cached/mock data for channels not supported by the current public
    client abstraction.
    """

    name = "bitso"

    def __init__(
        self, client: BitsoClient | None = None, cache: MarketDataCache | None = None
    ) -> None:
        super().__init__(cache)
        self.client = client or BitsoClient()

    async def get_ticker(self, book: str) -> Ticker:
        data = await self.client.ticker(book)
        payload: dict[str, Any] = data.get("payload", data)
        last = D(payload.get("last"))
        high = D(payload.get("high", last))
        low = D(payload.get("low", last))
        volume = D(payload.get("volume", 0))
        vwap = D(payload.get("vwap", last)) or last
        ticker = Ticker(book, last, high, low, volume, vwap, source=self.name)
        self.cache.update_ticker(ticker)
        self._event("ticker_updated", book, "ticker updated")
        return ticker

    async def get_orderbook(self, book: str) -> OrderBook:
        # BitsoClient currently exposes ticker-only public reads in this codebase.
        ticker = self.cache.tickers.get(book) or await self.get_ticker(book)
        bid = max(ticker.last - Decimal("1"), Decimal("0"))
        ask = ticker.last + Decimal("1")
        orderbook = OrderBook(
            book,
            (OrderBookLevel(bid, Decimal("0")),),
            (OrderBookLevel(ask, Decimal("0")),),
            source="bitso_read_only_synthetic_from_ticker",
        )
        self.cache.update_orderbook(orderbook)
        self._event(
            "orderbook_updated", book, "orderbook approximated from public ticker"
        )
        return orderbook

    async def get_candles(
        self, book: str, timeframe: str = "1m", limit: int = 100
    ) -> list[Candle]:
        ticker = self.cache.tickers.get(book) or await self.get_ticker(book)
        now = utc_now().replace(microsecond=0)
        candles = [
            Candle(
                book,
                timeframe,
                now - timedelta(minutes=limit - idx),
                ticker.last,
                ticker.high,
                ticker.low,
                ticker.last,
                ticker.volume,
            )
            for idx in range(limit)
        ]
        for candle in candles:
            self.cache.add_candle(candle)
        self._event(
            "candle_closed",
            book,
            "candles derived from public ticker",
            {"count": limit},
        )
        return candles

    async def get_recent_trades(self, book: str, limit: int = 100) -> list[MarketTrade]:
        ticker = self.cache.tickers.get(book) or await self.get_ticker(book)
        trades = [
            MarketTrade(book, ticker.last, Decimal("0"), "unknown", utc_now(), None)
            for _ in range(limit)
        ]
        for trade in trades:
            self.cache.add_trade(trade)
        return trades

    def status(self) -> ProviderStatus:
        status = super().status()
        return ProviderStatus(
            status.provider,
            status.connected,
            True,
            False,
            status.subscriptions,
            status.reconnects,
            status.last_heartbeat_at,
            status.last_error,
            status.uptime_seconds,
        )
