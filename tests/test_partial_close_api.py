"""API coverage for partial simulated position closes."""

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")

pytestmark = pytest.mark.database


def test_partial_close_keeps_remaining_position_and_records_sell(client):
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200

    opened = client.post(
        "/api/orders",
        json={
            "book": "btc_mxn",
            "side": "buy",
            "amount_mxn": "100.00",
            "daily_pnl_mxn": "0.00",
            "open_orders": 0,
        },
    )
    assert opened.status_code == 200
    position_id = opened.json()["id"]

    partial = client.post(
        f"/api/simulations/{position_id}/partial-close",
        json={"amount_mxn": "40.00"},
    )
    assert partial.status_code == 200
    payload = partial.json()
    assert payload["status"] == "partially_closed"
    assert payload["closed_lot"]["amount_mxn"] == 40.0
    assert payload["remaining_position"]["amount_mxn"] == 60.0
    assert payload["closed_lot"]["parent_position_id"] == position_id

    positions = client.get("/api/positions")
    assert positions.status_code == 200
    remaining = [item for item in positions.json()["items"] if item["id"] == position_id]
    assert len(remaining) == 1
    assert remaining[0]["amount_mxn"] == 60.0

    events = client.get("/api/orders?limit=10&offset=0").json()["items"]
    assert [event["side"] for event in events[:2]] == ["sell", "buy"]
    assert events[0]["amount_mxn"] == 40.0
    assert events[0]["reason"] == "manual_partial_close"
    assert events[0]["correlation_id"] == position_id


def test_partial_close_rejects_full_or_excess_amount(client):
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200
    opened = client.post(
        "/api/orders",
        json={"book": "eth_mxn", "side": "buy", "amount_mxn": "100.00"},
    )
    position_id = opened.json()["id"]

    response = client.post(
        f"/api/simulations/{position_id}/partial-close",
        json={"amount_mxn": "100.00"},
    )
    assert response.status_code == 422
    assert "Cerrar posición" in response.json()["detail"]
