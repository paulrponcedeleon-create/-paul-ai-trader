from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.unified_markets import UnifiedMarketService


class FakeBitsoClient:
    def __init__(self) -> None:
        self.place_order_calls = 0
        self.ticker_calls = 0
        self.fee_calls = 0
        self.available_books_calls = 0
        self.taker_fee_rate = 0.0078
        self.prices: dict[str, float] = {
            "btc_mxn": 1_000_000.0,
            "eth_mxn": 35_000.0,
            "sol_mxn": 1_500.0,
            "atom_mxn": 90.0,
            "xrp_mxn": 20.0,
            "paxg_mxn": 50_000.0,
            "usdc_mxn": 18.0,
            "usdt_mxn": 18.1,
        }
        self.range_24_pct: dict[str, float] = {
            "btc_mxn": 4.0,
            "eth_mxn": 6.0,
            "sol_mxn": 9.0,
            "atom_mxn": 7.0,
            "xrp_mxn": 8.0,
            "paxg_mxn": 2.0,
            "usdc_mxn": 1.0,
            "usdt_mxn": 1.2,
        }
        self.last_position: dict[str, float] = {
            "btc_mxn": 0.90,
            "eth_mxn": 0.50,
            "sol_mxn": 0.10,
            "atom_mxn": 0.50,
            "xrp_mxn": 0.88,
            "paxg_mxn": 0.50,
            "usdc_mxn": 0.50,
            "usdt_mxn": 0.50,
        }
        self.fee_rates: dict[str, float] = {
            book: (0.0036 if book in {"usdc_mxn", "usdt_mxn"} else self.taker_fee_rate)
            for book in self.prices
        }

    async def ticker(self, book: str) -> dict[str, Any]:
        self.ticker_calls += 1
        last = self.prices[book]
        range_pct = self.range_24_pct.get(book, 4.0) / 100
        position = self.last_position.get(book, 0.5)
        width = last * range_pct
        low = last - width * position
        high = low + width
        return {
            "payload": {
                "book": book,
                "last": str(last),
                "high": str(high),
                "low": str(low),
                "change_24": "0",
                "volume": "10",
            }
        }

    async def available_books(self) -> dict[str, Any]:
        self.available_books_calls += 1
        return {
            "success": True,
            "payload": [{"book": book} for book in self.prices],
        }

    async def balance(self) -> dict[str, Any]:
        return {"success": True, "payload": {"balances": []}}

    async def fees(self) -> dict[str, Any]:
        self.fee_calls += 1
        return {
            "success": True,
            "payload": {
                "fees": [
                    {
                        "book": book,
                        "taker_fee_decimal": str(self.fee_rates[book]),
                        "taker_fee_percent": str(self.fee_rates[book] * 100),
                    }
                    for book in self.prices
                ]
            },
        }

    async def place_market_order(
        self, book: str, side: str, amount_mxn: float
    ) -> dict[str, Any]:
        self.place_order_calls += 1
        return {"success": True, "book": book, "side": side, "amount_mxn": amount_mxn}


class FakeStockQuoteClient:
    prices = {
        "ALGN": 180.0,
        "PSTG": 70.0,
        "TSLA": 320.0,
        "AAPL": 220.0,
    }
    positions = {
        "ALGN": 0.90,
        "PSTG": 0.50,
        "TSLA": 0.10,
        "AAPL": 0.50,
    }

    async def quote(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.upper()
        last = self.prices[symbol]
        width = last * 0.05
        low = last - width * self.positions[symbol]
        return {
            "symbol": symbol,
            "last": last,
            "high": low + width,
            "low": low,
            "volume": 1000,
            "previous_close": last * 0.99,
            "currency": "USD",
            "exchange": "US",
            "source": "fake_stock_reference",
            "delayed": False,
        }


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        app_password="test-password",
        session_secret="test-session-secret-with-more-than-32-characters",
        session_cookie_secure=False,
        live_trading=False,
    )


@pytest.fixture
def fake_bitso() -> FakeBitsoClient:
    return FakeBitsoClient()


@pytest.fixture
def fake_stocks() -> FakeStockQuoteClient:
    return FakeStockQuoteClient()


@pytest.fixture
def client(
    test_settings: Settings,
    fake_bitso: FakeBitsoClient,
    fake_stocks: FakeStockQuoteClient,
    tmp_path: Path,
):
    test_settings.database_url = f"sqlite:///{tmp_path / 'simulations.db'}"
    application = create_app(test_settings, fake_bitso)
    application.state.unified_markets = UnifiedMarketService(fake_bitso, fake_stocks)
    with TestClient(application) as test_client:
        yield test_client
