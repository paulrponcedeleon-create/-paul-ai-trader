from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from app.market_data.models import (
    Candle,
    MarketDataEvent,
    MarketTrade,
    OrderBook,
    Ticker,
)


@dataclass
class MarketDataCache:
    max_candles: int = 500
    max_trades: int = 500
    max_events: int = 500
    tickers: dict[str, Ticker] = field(default_factory=dict)
    orderbooks: dict[str, OrderBook] = field(default_factory=dict)
    candles: dict[tuple[str, str], Deque[Candle]] = field(default_factory=dict)
    trades: dict[str, Deque[MarketTrade]] = field(default_factory=dict)
    events: Deque[MarketDataEvent] = field(default_factory=deque)

    def update_ticker(self, ticker: Ticker) -> None:
        self.tickers[ticker.book] = ticker

    def update_orderbook(self, orderbook: OrderBook) -> None:
        self.orderbooks[orderbook.book] = orderbook

    def add_candle(self, candle: Candle) -> None:
        key = (candle.book, candle.timeframe)
        self.candles.setdefault(key, deque(maxlen=self.max_candles)).append(candle)

    def add_trade(self, trade: MarketTrade) -> None:
        self.trades.setdefault(trade.book, deque(maxlen=self.max_trades)).append(trade)

    def add_event(self, event: MarketDataEvent) -> None:
        self.events.append(event)
        while len(self.events) > self.max_events:
            self.events.popleft()

    def latest_candles(
        self, book: str, timeframe: str, limit: int = 100
    ) -> list[Candle]:
        values = list(self.candles.get((book, timeframe), []))
        return values[-limit:]

    def recent_trades(self, book: str, limit: int = 100) -> list[MarketTrade]:
        return list(self.trades.get(book, []))[-limit:]
