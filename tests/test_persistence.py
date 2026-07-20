from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.repositories.simulated_orders import SqlSimulatedOrderRepository


def test_sql_repository_persists_simulated_orders(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'repo.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as session:
        repository = SqlSimulatedOrderRepository(session)
        created = repository.add(
            {
                "id": "sim-1",
                "created_at": datetime.now(timezone.utc),
                "status": "simulated",
                "book": "btc_mxn",
                "side": "buy",
                "amount_mxn": 100,
                "risk_check": "Orden dentro de límites.",
            }
        )
        session.commit()

    with Session() as session:
        repository = SqlSimulatedOrderRepository(session)
        items = repository.list()

    assert created["id"] == "sim-1"
    assert items[0]["id"] == "sim-1"
    assert items[0]["book"] == "btc_mxn"


def test_sql_repository_lists_stable_pages_and_total(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'pages.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    start = datetime(2026, 7, 20, tzinfo=timezone.utc)

    with Session() as session:
        repository = SqlSimulatedOrderRepository(session)
        for index in range(5):
            repository.add(
                {
                    "id": f"sim-{index}",
                    "created_at": start + timedelta(minutes=index),
                    "status": "simulated",
                    "book": "btc_mxn",
                    "side": "buy",
                    "amount_mxn": 10 + index,
                    "risk_check": "Orden dentro de límites.",
                }
            )
        session.commit()

    with Session() as session:
        repository = SqlSimulatedOrderRepository(session)
        first_page = repository.list(limit=2, offset=0)
        second_page = repository.list(limit=2, offset=2)
        total = repository.count()

    assert [item["id"] for item in first_page] == ["sim-4", "sim-3"]
    assert [item["id"] for item in second_page] == ["sim-2", "sim-1"]
    assert total == 5


def test_api_simulation_history_is_paginated(client: TestClient):
    client.post("/api/login", json={"password": "test-password"})

    for index in range(23):
        order = client.post(
            "/api/orders",
            json={
                "book": "btc_mxn",
                "side": "buy",
                "amount_mxn": 10 + index,
            },
        )
        assert order.status_code == 200

    first = client.get("/api/simulations?limit=10&offset=0")
    second = client.get("/api/simulations?limit=10&offset=10")
    third = client.get("/api/simulations?limit=10&offset=20")

    assert first.status_code == 200
    assert first.json()["total"] == 23
    assert len(first.json()["items"]) == 10
    assert first.json()["has_more"] is True
    assert first.json()["next_offset"] == 10

    assert len(second.json()["items"]) == 10
    assert second.json()["has_more"] is True
    assert second.json()["next_offset"] == 20

    assert len(third.json()["items"]) == 3
    assert third.json()["has_more"] is False
    assert third.json()["next_offset"] is None

    all_ids = [
        item["id"]
        for page in (first.json(), second.json(), third.json())
        for item in page["items"]
    ]
    assert len(all_ids) == len(set(all_ids)) == 23
    assert client.get("/api/simulations?limit=101").status_code == 422


def test_live_simulated_position_tracks_and_closes_pnl(client, fake_bitso):
    client.post("/api/login", json={"password": "test-password"})
    fake_bitso.prices["btc_mxn"] = 100.0

    opened = client.post(
        "/api/orders",
        json={"book": "btc_mxn", "side": "buy", "amount_mxn": 100},
    )

    assert opened.status_code == 200
    opened_data = opened.json()
    assert opened_data["status"] == "simulated"
    assert opened_data["position_status"] == "open"
    assert opened_data["reference_price"] == 100.0
    assert opened_data["asset_quantity"] == 1.0

    fake_bitso.prices["btc_mxn"] = 110.0
    positions = client.get("/api/positions")

    assert positions.status_code == 200
    position = positions.json()["items"][0]
    summary = positions.json()["summary"]
    assert position["current_price"] == 110.0
    assert position["current_value_mxn"] == 110.0
    assert position["unrealized_pnl_mxn"] == 10.0
    assert position["return_pct"] == 10.0
    assert summary == {
        "open_positions": 1,
        "invested_mxn": 100.0,
        "current_value_mxn": 110.0,
        "unrealized_pnl_mxn": 10.0,
        "return_pct": 10.0,
    }
    assert positions.json()["fees_included"] is False

    closed = client.post(f"/api/simulations/{opened_data['id']}/close")

    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert closed.json()["close_price"] == 110.0
    assert closed.json()["realized_pnl_mxn"] == 10.0
    assert closed.json()["return_pct"] == 10.0

    no_open_positions = client.get("/api/positions")
    assert no_open_positions.json()["items"] == []
    assert no_open_positions.json()["summary"]["open_positions"] == 0

    history = client.get("/api/simulations")
    assert history.json()["items"][0]["status"] == "closed"
    assert history.json()["items"][0]["realized_pnl_mxn"] == 10.0
    assert client.post(f"/api/simulations/{opened_data['id']}/close").status_code == 404


def test_api_simulation_survives_application_restart(test_settings, fake_bitso, tmp_path):
    db_url = f"sqlite:///{tmp_path / 'api.db'}"
    test_settings.database_url = db_url

    from app.main import create_app

    first_app = create_app(test_settings, fake_bitso)
    with TestClient(first_app) as first_client:
        assert first_client.get("/health").json() == {"status": "ok", "mode": "simulation"}
        login = first_client.post("/api/login", json={"password": "test-password"})
        assert login.status_code == 200
        order = first_client.post(
            "/api/orders",
            json={"book": "btc_mxn", "side": "buy", "amount_mxn": 100},
        )
        assert order.status_code == 200
        created_id = order.json()["id"]

    second_app = create_app(test_settings, fake_bitso)
    with TestClient(second_app) as second_client:
        second_client.post("/api/login", json={"password": "test-password"})
        history = second_client.get("/api/simulations")
        positions = second_client.get("/api/positions")

    assert history.status_code == 200
    assert history.json()["items"][0]["id"] == created_id
    assert history.json()["total"] == 1
    assert history.json()["has_more"] is False
    assert positions.json()["items"][0]["id"] == created_id
    assert fake_bitso.place_order_calls == 0
