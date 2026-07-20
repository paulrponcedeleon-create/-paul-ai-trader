from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeBitsoClient:
    def __init__(self) -> None:
        self.place_order_calls = 0
        self.ticker_calls = 0
        self.fee_calls = 0
        self.available_books_calls = 0
        self.taker_fee_rate = 0.0078
        self.prices: dict[str, float] = {
            "btc_mxn": 100.0,
            "eth_mxn": 100.0,
            "sol_mxn": 100.0,
            "xrp_mxn": 100.0,
            "doge_mxn": 10.0,
            "ada_mxn": 20.0,
            "shib_mxn": 0.001,
            "pepe_mxn": 0.0002,
        }
        self.range_24_pct: dict[str, float] = {
            "btc_mxn": 4.0,
            "eth_mxn": 6.0,
            "sol_mxn": 9.0,
            "xrp_mxn": 8.0,
            "doge_mxn": 14.0,
            "ada_mxn": 7.0,
            "shib_mxn": 18.0,
            "pepe_mxn": 22.0,
        }
        self.fee_rates: dict[str, float] = {
            book: self.taker_fee_rate for book in self.prices
        }
        self.fee_rates["doge_mxn"] = 0.0065

    async def ticker(self, book: str) -> dict[str, Any]:
        self.ticker_calls += 1
        last = self.prices.get(book, 100.0)
        range_pct = self.range_24_pct.get(book, 20.0) / 100
        return {
            "payload": {
                "book": book,
                "last": str(last),
                "high": str(last * (1 + range_pct / 2)),
                "low": str(last * (1 - range_pct / 2)),
                "change_24": str(last * 0.02),
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
                        "taker_fee_decimal": str(self.fee_rates.get(book, self.taker_fee_rate)),
                        "taker_fee_percent": str(
                            self.fee_rates.get(book, self.taker_fee_rate) * 100
                        ),
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
def client(
    test_settings: Settings,
    fake_bitso: FakeBitsoClient,
    tmp_path: Path,
):
    test_settings.database_url = f"sqlite:///{tmp_path / 'simulations.db'}"
    application = create_app(test_settings, fake_bitso)
    with TestClient(application) as test_client:
        yield test_client
