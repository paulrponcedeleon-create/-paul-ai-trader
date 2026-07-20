from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeBitsoClient:
    def __init__(self) -> None:
        self.place_order_calls = 0

    async def ticker(self, book: str) -> dict[str, Any]:
        return {
            "payload": {
                "book": book,
                "last": "100",
                "high": "110",
                "low": "90",
                "volume": "10",
            }
        }

    async def balance(self) -> dict[str, Any]:
        return {"success": True, "payload": {"balances": []}}

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
