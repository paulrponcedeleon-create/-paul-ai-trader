from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.unified_markets import UnifiedMarketService
from tests.conftest import FakeBitsoClient, FakeStockQuoteClient


EXPECTED_SYMBOLS = [
    "BTC",
    "ETH",
    "SOL",
    "ATOM",
    "MXN",
    "USD",
    "USDT",
    "PAXG",
    "XRP",
    "ALGN",
    "PSTG",
    "TSLA",
    "AAPL",
]


def test_curated_market_catalog_has_visual_signals_and_exact_assets(client):
    assert client.get("/api/markets").status_code == 401
    client.post("/api/login", json={"password": "test-password"})

    response = client.get("/api/markets")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 13
    assert [item["symbol"] for item in data["items"]] == EXPECTED_SYMBOLS

    actions = {item["symbol"]: item["signal"]["action"] for item in data["items"]}
    assert actions["BTC"] == "buy"
    assert actions["SOL"] == "sell"
    assert actions["ETH"] == "hold"
    assert actions["ATOM"] == "hold"
    assert actions["PAXG"] == "hold"
    assert actions["MXN"] == "hold"
    assert actions["ALGN"] == "buy"
    assert actions["TSLA"] == "sell"

    by_symbol = {item["symbol"]: item for item in data["items"]}
    assert by_symbol["BTC"]["effective_fee_percent"] == 0.78
    assert by_symbol["USD"]["effective_fee_percent"] == 0.36
    assert by_symbol["ALGN"]["effective_fee_percent"] == 0.0
    assert by_symbol["PSTG"]["name"] == "Everpure, Inc."
    assert by_symbol["MXN"]["tradeable"] is False

    assert by_symbol["ATOM"]["available"] is True
    assert by_symbol["ATOM"]["tradeable"] is True
    assert by_symbol["ATOM"]["source"] == "bitso_rfq"
    assert by_symbol["ATOM"]["fee_included_in_quote"] is True
    assert by_symbol["ATOM"]["route_label"] == "Conversión Bitso App · MXN → ATOM"

    assert by_symbol["PAXG"]["available"] is True
    assert by_symbol["PAXG"]["source"] == "bitso_rfq"
    assert by_symbol["PAXG"]["route_label"] == "Conversión Bitso App · MXN → PAXG"


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


def test_atom_simulation_uses_bitso_app_buy_and_sell_quotes(client):
    client.post("/api/login", json={"password": "test-password"})

    opened = client.post(
        "/api/orders",
        json={"book": "atom_mxn", "side": "buy", "amount_mxn": 100},
    )
    positions = client.get("/api/positions")

    assert opened.status_code == 200
    opened_data = opened.json()
    assert opened_data["symbol"] == "ATOM"
    assert opened_data["reference_price"] == 90.0
    assert opened_data["entry_fee_mxn"] == 0.0
    assert opened_data["fee_included_in_quote"] is True
    assert opened_data["route_label"] == "Conversión Bitso App · MXN → ATOM"

    assert positions.status_code == 200
    item = positions.json()["items"][0]
    assert item["symbol"] == "ATOM"
    assert item["current_price"] == 89.1
    assert item["current_value_mxn"] == 99.0
    assert item["unrealized_pnl_mxn"] == -1.0
    assert item["total_estimated_fees_mxn"] == 0.0
    assert item["fee_included_in_quote"] is True
    assert item["route_label"] == "Conversión Bitso App · ATOM → MXN"


def test_stock_simulation_uses_mxn_reference_and_zero_trading_fee(client):
    client.post("/api/login", json={"password": "test-password"})

    opened = client.post(
        "/api/orders",
        json={"book": "pstg_mxn", "side": "buy", "amount_mxn": 100},
    )
    positions = client.get("/api/positions")

    assert opened.status_code == 200
    assert opened.json()["symbol"] == "PSTG"
    assert opened.json()["name"] == "Everpure, Inc."
    assert opened.json()["reference_price"] == 1260.0
    assert opened.json()["entry_fee_mxn"] == 0.0

    assert positions.status_code == 200
    item = positions.json()["items"][0]
    assert item["symbol"] == "PSTG"
    assert item["asset_type"] == "stock"
    assert item["current_value_mxn"] == 100.0
    assert item["total_estimated_fees_mxn"] == 0.0


def test_curated_extra_assets_are_simulation_only(tmp_path: Path):
    simulation_settings = Settings(
        _env_file=None,
        app_env="test",
        app_password="test-password",
        session_secret="test-session-secret-with-more-than-32-characters",
        session_cookie_secure=False,
        live_trading=False,
        database_url=f"sqlite:///{tmp_path / 'simulation.db'}",
    )
    assert "pstg_mxn" in simulation_settings.allowed_books_set
    assert "atom_mxn" in simulation_settings.allowed_books_set

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
    assert "pstg_mxn" not in live_settings.allowed_books_set

    fake_bitso = FakeBitsoClient()
    app = create_app(live_settings, fake_bitso)
    app.state.unified_markets = UnifiedMarketService(
        fake_bitso, FakeStockQuoteClient()
    )
    with TestClient(app) as live_client:
        live_client.post("/api/login", json={"password": "test-password"})
        blocked = live_client.post(
            "/api/orders",
            json={"book": "pstg_mxn", "side": "buy", "amount_mxn": 100},
        )

    assert blocked.status_code == 403
    assert fake_bitso.place_order_calls == 0
