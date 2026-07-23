import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import FakeBitsoClient


EXPECTED_SYMBOLS = [
    "BTC",
    "ETH",
    "SOL",
    "USDT",
    "XRP",
    "ALGN",
    "TSLA",
    "AAPL",
]


def test_curated_market_catalog_has_visual_signals_and_verified_assets(client):
    assert client.get("/api/markets").status_code == 401
    client.post("/api/login", json={"password": "test-password"})

    response = client.get("/api/markets")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == len(EXPECTED_SYMBOLS)
    assert [item["symbol"] for item in data["items"]] == EXPECTED_SYMBOLS

    actions = {item["symbol"]: item["signal"]["action"] for item in data["items"]}
    assert actions["BTC"] == "buy"
    assert actions["SOL"] == "sell"
    assert actions["ETH"] == "hold"
    assert actions["ALGN"] == "buy"
    assert actions["TSLA"] == "sell"

    by_symbol = {item["symbol"]: item for item in data["items"]}
    assert by_symbol["BTC"]["effective_fee_percent"] == 0.78
    assert by_symbol["USDT"]["effective_fee_percent"] == 0.36
    assert by_symbol["ALGN"]["effective_fee_percent"] == 0.0
    assert by_symbol["ALGN"]["asset_type"] == "stock"
    assert by_symbol["ALGN"]["tradeable"] is True

    for removed in {"ATOM", "MXN", "USD", "PAXG", "PSTG"}:
        assert removed not in by_symbol


def test_curated_catalog_uses_short_server_cache(client, fake_bitso):
    client.post("/api/login", json={"password": "test-password"})

    first = client.get("/api/markets")
    calls_after_first = (
        fake_bitso.available_books_calls,
        fake_bitso.fee_calls,
        fake_bitso.ticker_calls,
        fake_bitso.rfq_pairs_calls,
        fake_bitso.rfq_quote_calls,
    )
    second = client.get("/api/markets")

    assert first.status_code == second.status_code == 200
    assert calls_after_first == (
        fake_bitso.available_books_calls,
        fake_bitso.fee_calls,
        fake_bitso.ticker_calls,
        fake_bitso.rfq_pairs_calls,
        fake_bitso.rfq_quote_calls,
    )


def test_removed_rfq_asset_is_blocked_from_new_simulations(client):
    client.post("/api/login", json={"password": "test-password"})

    opened = client.post(
        "/api/orders",
        json={"book": "atom_mxn", "side": "buy", "amount_mxn": 100},
    )

    assert opened.status_code == 403
    assert "Mercado no autorizado" in opened.json()["detail"]


def test_verified_stock_simulation_uses_reference_and_zero_trading_fee(client):
    client.post("/api/login", json={"password": "test-password"})

    opened = client.post(
        "/api/orders",
        json={"book": "algn_mxn", "side": "buy", "amount_mxn": 100},
    )
    positions = client.get("/api/positions")

    assert opened.status_code == 200
    assert opened.json()["symbol"] == "ALGN"
    assert opened.json()["name"] == "Align Technology"
    assert opened.json()["entry_fee_mxn"] == 0.0

    assert positions.status_code == 200
    item = positions.json()["items"][0]
    assert item["symbol"] == "ALGN"
    assert item["asset_type"] == "stock"
    assert item["total_estimated_fees_mxn"] == 0.0


def test_allowed_books_are_restricted_in_simulation_and_live(tmp_path: Path):
    simulation_settings = Settings(
        _env_file=None,
        app_env="test",
        app_password="test-password",
        session_secret="test-session-secret-with-more-than-32-characters",
        session_cookie_secure=False,
        live_trading=False,
        database_url=f"sqlite:///{tmp_path / 'simulation.db'}",
    )
    assert "algn_mxn" in simulation_settings.allowed_books_set
    assert "atom_mxn" not in simulation_settings.allowed_books_set
    assert "pstg_mxn" not in simulation_settings.allowed_books_set

    live_settings = Settings(
        _env_file=None,
        app_env="test",
        app_password="test-password",
        session_secret="test-session-secret-with-more-than-32-characters",
        session_cookie_secure=False,
        live_trading=True,
        database_url=f"sqlite:///{tmp_path / 'live.db'}",
        allowed_books="btc_mxn,eth_mxn,xrp_mxn,sol_mxn",
    )
    assert "algn_mxn" not in live_settings.allowed_books_set

    fake_bitso = FakeBitsoClient()
    app = create_app(live_settings, fake_bitso)
    with TestClient(app) as live_client:
        live_client.post("/api/login", json={"password": "test-password"})
        blocked = live_client.post(
            "/api/orders",
            json={"book": "algn_mxn", "side": "buy", "amount_mxn": 100},
        )

    assert blocked.status_code == 403
    assert fake_bitso.place_order_calls == 0
