from __future__ import annotations

from abc import ABC, abstractmethod

from app.market_data.models import (
    Candle,
    OrderBook,
    ProviderStatus,
    Ticker,
    MarketTrade,
)


class MarketDataProvider(ABC):
    name: str
    read_only: bool = True

    @abstractmethod
    async def connect(self) -> ProviderStatus: ...

    @abstractmethod
    async def disconnect(self) -> ProviderStatus: ...

    @abstractmethod
    def status(self) -> ProviderStatus: ...

    @abstractmethod
    async def subscribe(
        self, book: str, channels: tuple[str, ...] = ("ticker",)
    ) -> ProviderStatus: ...

    @abstractmethod
    async def get_ticker(self, book: str) -> Ticker: ...

    @abstractmethod
    async def get_candles(
        self, book: str, timeframe: str = "1m", limit: int = 100
    ) -> list[Candle]: ...

    @abstractmethod
    async def get_orderbook(self, book: str) -> OrderBook: ...

    @abstractmethod
    async def get_recent_trades(
        self, book: str, limit: int = 100
    ) -> list[MarketTrade]: ...
