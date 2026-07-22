from __future__ import annotations

from typing import Any

from app.market_data.cache import MarketDataCache
from app.market_data.mock import MockMarketDataProvider
from app.market_data.provider import MarketDataProvider


class ProviderFactory:
    def __init__(
        self,
        *,
        settings: Any | None = None,
        bitso_client: Any | None = None,
        cache: MarketDataCache | None = None,
    ) -> None:
        self.settings = settings
        self.bitso_client = bitso_client
        self.cache = cache or MarketDataCache()

    def create(self, name: str | None = None) -> MarketDataProvider:
        selected = (name or "mock").lower()
        if selected == "mock":
            return MockMarketDataProvider(self.cache)
        if selected == "bitso":
            from app.market_data.bitso import BitsoMarketDataProvider

            return BitsoMarketDataProvider(self.bitso_client, self.cache)
        raise ValueError("Proveedor de market data no soportado.")
