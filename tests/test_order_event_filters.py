from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("sqlalchemy")
pytestmark = pytest.mark.database

from app.repositories.order_events import SqlSimulatedOrderEventRepository


def test_order_event_filters_and_pagination(client):
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200
    session_factory = client.app.state.db_session_factory
    now = datetime.now(timezone.utc)
    rows = [
        ("evt-filter-1", "btc_mxn", "buy", "manual"),
        ("evt-filter-2", "btc_mxn", "sell", "runtime"),
        ("evt-filter-3", "eth_mxn", "sell", "automatic_exit"),
        ("evt-filter-4", "eth_mxn", "buy", "manual"),
    ]
    with session_factory() as session:
        repository = SqlSimulatedOrderEventRepository(session)
        for index, (event_id, book, side, source) in enumerate(rows):
            repository.add(
                {
                    "id": event_id,
                    "created_at": now + timedelta(seconds=index),
                    "position_id": f"pos-{index}",
                    "book": book,
                    "side": side,
                    "status": "filled",
                    "amount_mxn": "10.00",
                    "price": "100.00",
                    "fee_mxn": "0.10",
                    "source": source,
                    "reason": "test",
                }
            )
        session.commit()

    btc = client.get("/api/orders?books=btc_mxn&limit=10&offset=0").json()
    assert btc["total"] == 2
    assert {item["book"] for item in btc["items"]} == {"btc_mxn"}

    sells = client.get("/api/orders?side=sell&limit=10&offset=0").json()
    assert sells["total"] == 2
    assert all(item["side"] == "sell" for item in sells["items"])

    manual = client.get("/api/orders?source=manual&limit=10&offset=0").json()
    assert manual["total"] == 2
    assert all(item["source"] == "manual" for item in manual["items"])

    first_page = client.get("/api/orders?limit=2&offset=0").json()
    second_page = client.get("/api/orders?limit=2&offset=2").json()
    first_ids = [item["id"] for item in first_page["items"]]
    second_ids = [item["id"] for item in second_page["items"]]
    assert first_page["has_more"] is True
    assert first_page["next_offset"] == 2
    assert set(first_ids).isdisjoint(second_ids)
    assert first_ids == ["evt-filter-4", "evt-filter-3"]
