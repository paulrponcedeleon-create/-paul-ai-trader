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
        self.taker_fee_rate = 0.0078
        self.prices: dict[str, float] = {
            "btc_mxn": 100.0,
            "eth_mxn": 100.0,
            "sol_mxn": 100.0,
            "xrp_mxn": 100.0,
        }

    async def ticker(self, book: str) -> dict[str, Any]:
        self.ticker_calls += 1
        last = self.prices.get(book, 100.0)
        return {
            "payload": {
                "book": book,
                "last": str(last),
                "high": str(last * 1.1),
                "low": str(last * 0.9),
                "volume": "10",
            }
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
                        "taker_fee_decimal": str(self.taker_fee_rate),
                        "taker_fee_percent": str(self.taker_fee_rate * 100),
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
