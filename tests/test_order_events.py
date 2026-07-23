from __future__ import annotations

from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.brokers.persistent_paper import PersistentPaperBroker
from app.config import Settings
from app.main import create_app

pytestmark = pytest.mark.database


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        app_password="test-password",
        session_secret="test-session-secret-with-more-than-32-characters",
        session_cookie_secure=False,
        database_url=f"sqlite:///{tmp_path / 'order-events.db'}",
        paul_data_dir=str(tmp_path / "data"),
        live_trading=False,
        runtime_auto_start=False,
        runtime_broker="paper",
        simulated_initial_capital_mxn=5000.0,
    )


def test_manual_buy_and_close_create_separate_buy_sell_events(client):
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200

    opened = client.post(
        "/api/orders",
        json={
            "book": "btc_mxn",
            "side": "buy",
            "amount_mxn": 100,
            "daily_pnl_mxn": 0,
            "open_orders": 0,
        },
    )
    assert opened.status_code == 200
    position_id = opened.json()["id"]

    buy_events = client.get("/api/orders?limit=10&offset=0")
    assert buy_events.status_code == 200
    payload = buy_events.json()
    assert payload["total"] == 1
    assert payload["items"][0]["side"] == "buy"
    assert payload["items"][0]["position_id"] == position_id
    assert payload["items"][0]["source"] == "manual"

    closed = client.post(f"/api/simulations/{position_id}/close")
    assert closed.status_code == 200

    events = client.get("/api/orders?limit=10&offset=0").json()
    assert events["total"] == 2
    assert [item["side"] for item in events["items"]] == ["sell", "buy"]
    assert events["items"][0]["position_id"] == position_id
    assert events["items"][0]["reason"] == "manual_close"
    assert events["items"][0]["realized_pnl_mxn"] is not None


def test_runtime_buy_and_sell_create_automatic_order_events(tmp_path, fake_bitso):
    settings = _settings(tmp_path)
    application = create_app(settings, fake_bitso)

    with TestClient(application) as client:
        assert client.post("/api/login", json={"password": "test-password"}).status_code == 200
        broker = PersistentPaperBroker(
            session_factory=application.state.db_session_factory,
            settings=settings,
        )
        broker.connect()
        opened = broker.place_market_buy(
            book="btc_mxn",
            amount_mxn=Decimal("100"),
            price=Decimal("1000"),
        )
        assert opened.status == "filled"
        sold = broker.place_market_sell(
            book="btc_mxn",
            amount_mxn=Decimal("100"),
            price=Decimal("1100"),
        )
        assert sold.status == "filled"

        events = client.get("/api/orders?limit=10&offset=0").json()["items"]
        assert [event["side"] for event in events] == ["sell", "buy"]
        assert all(event["source"] == "runtime" for event in events)
        assert events[0]["reason"] == "strategy_sell"
        assert events[0]["realized_pnl_mxn"] == 10.0


def test_release_endpoint_and_dashboard_expose_deployed_version(client, monkeypatch):
    monkeypatch.setenv("APP_RELEASE", "Gate 1 Test")
    monkeypatch.setenv("RENDER_GIT_BRANCH", "v2-dashboard")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "1234567890abcdef")
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200

    release = client.get("/api/release")
    assert release.status_code == 200
    assert release.json() == {
        "release": "Gate 1 Test",
        "branch": "v2-dashboard",
        "commit": "12345678",
        "mode": "simulation",
    }

    html = client.get("/").text
    assert "Últimas 10 órdenes BUY / SELL" in html
    assert 'id="orderEvents"' in html
    assert 'id="releaseMarker"' in html
    assert "/static/order-events.css" in html
    assert "/static/order-events.js" in html
