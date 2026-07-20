from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import FakeBitsoClient


def test_market_catalog_discovers_only_real_bitso_books(client, fake_bitso):
    assert client.get("/api/markets").status_code == 401
    client.post("/api/login", json={"password": "test-password"})

    response = client.get("/api/markets")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == len(fake_bitso.prices)
    assert data["discovery_source"] == "bitso_available_books"
    assert data["fee_source"] == "bitso_account"
    assert data["items"][0]["book"] == "pepe_mxn"
    assert data["items"][0]["range_24_pct"] == 22.0
    assert "Alta volatilidad" in data["items"][0]["tags"]

    doge = next(item for item in data["items"] if item["book"] == "doge_mxn")
    btc = next(item for item in data["items"] if item["book"] == "btc_mxn")
    assert doge["taker_fee_percent"] == 0.65
    assert "Comisión menor" in doge["tags"]
    assert "Principal" in btc["tags"]
    assert all(item["book"] != "aave_mxn" for item in data["items"])


def test_market_catalog_uses_short_server_cache(client, fake_bitso):
    client.post("/api/login", json={"password": "test-password"})

    first = client.get("/api/markets")
    second = client.get("/api/markets")

    assert first.status_code == second.status_code == 200
    assert fake_bitso.available_books_calls == 1
    assert fake_bitso.fee_calls == 1


def test_expanded_markets_are_simulation_only(tmp_path: Path):
    simulation_settings = Settings(
        _env_file=None,
        app_env="test",
        app_password="test-password",
        session_secret="test-session-secret-with-more-than-32-characters",
        session_cookie_secure=False,
        live_trading=False,
        database_url=f"sqlite:///{tmp_path / 'simulation.db'}",
    )
    assert "doge_mxn" in simulation_settings.allowed_books_set

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
    assert "doge_mxn" not in live_settings.allowed_books_set

    fake = FakeBitsoClient()
    app = create_app(live_settings, fake)
    with TestClient(app) as live_client:
        live_client.post("/api/login", json={"password": "test-password"})
        blocked = live_client.post(
            "/api/orders",
            json={"book": "doge_mxn", "side": "buy", "amount_mxn": 100},
        )

    assert blocked.status_code == 403
    assert fake.place_order_calls == 0
