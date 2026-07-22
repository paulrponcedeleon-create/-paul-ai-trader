from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.market_data.models import ProviderStatus
from app.market_data.provider import MarketDataProvider


@dataclass
class WebSocketController:
    provider: MarketDataProvider
    heartbeat_seconds: float = 30.0
    backoff_initial_seconds: float = 1.0
    backoff_max_seconds: float = 30.0
    subscriptions: set[tuple[str, tuple[str, ...]]] | None = None

    def __post_init__(self) -> None:
        if self.subscriptions is None:
            self.subscriptions = set()
        self.backoff_seconds = self.backoff_initial_seconds

    async def connect(self) -> ProviderStatus:
        status = await self.provider.connect()
        await self.resubscribe()
        self.backoff_seconds = self.backoff_initial_seconds
        return status

    async def disconnect(self) -> ProviderStatus:
        return await self.provider.disconnect()

    async def subscribe(self, book: str, channels: tuple[str, ...]) -> ProviderStatus:
        assert self.subscriptions is not None
        self.subscriptions.add((book, channels))
        return await self.provider.subscribe(book, channels)

    async def heartbeat(self) -> ProviderStatus:
        heartbeat = getattr(self.provider, "heartbeat", None)
        if heartbeat is not None:
            return await heartbeat()
        return self.provider.status()

    async def reconnect(self) -> ProviderStatus:
        await asyncio.sleep(0)
        reconnect = getattr(self.provider, "reconnect", None)
        if reconnect is not None:
            status = await reconnect()
        else:
            await self.provider.disconnect()
            status = await self.provider.connect()
        await self.resubscribe()
        self.backoff_seconds = min(self.backoff_seconds * 2, self.backoff_max_seconds)
        return status

    async def resubscribe(self) -> None:
        assert self.subscriptions is not None
        for book, channels in sorted(self.subscriptions):
            await self.provider.subscribe(book, channels)
