from datetime import datetime, timezone

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

    assert history.status_code == 200
    assert history.json()["items"][0]["id"] == created_id
    assert fake_bitso.place_order_calls == 0
