import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api

from fastapi.testclient import TestClient

from tests.conftest import FakeBitsoClient


def test_health_behavior_remains_unchanged(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "simulation"}


def test_dashboard_behavior_remains_available(client: TestClient):
    response = client.get("/")

    assert response.status_code == 200
    assert "Centro de control" in response.text
    assert "APRENDIZAJE ACELERADO" in response.text
    assert "DINERO REAL ACTIVO" not in response.text


def test_simulation_mode_never_calls_real_bitso_order(
    client: TestClient, fake_bitso: FakeBitsoClient
):
    client.post("/api/login", json={"password": "test-password"})

    response = client.post(
        "/api/orders",
        json={
            "book": "btc_mxn",
            "side": "buy",
            "amount_mxn": 100,
            "daily_pnl_mxn": 0,
            "open_orders": 0,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "simulated"
    assert fake_bitso.place_order_calls == 0


def test_market_endpoint_keeps_current_contract(client: TestClient):
    client.post("/api/login", json={"password": "test-password"})

    response = client.get("/api/market/btc_mxn")

    assert response.status_code == 200
    assert response.json()["book"] == "btc_mxn"
    assert response.json()["signal"]["action"] in {"buy", "sell", "hold"}
