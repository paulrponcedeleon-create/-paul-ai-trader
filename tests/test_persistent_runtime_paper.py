from __future__ import annotations

from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.api.routes import runtime as runtime_routes
from app.brokers.persistent_paper import PersistentPaperBroker
from app.config import Settings
from app.db.base import Base
from app.db.session import build_engine, build_session_factory
from app.main import create_app
from app.repositories.simulated_orders import SqlSimulatedOrderRepository

pytestmark = pytest.mark.database


def _settings(tmp_path, *, initial_capital: float = 1000.0) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        app_password="test-password",
        session_secret="test-session-secret-with-more-than-32-characters",
        session_cookie_secure=False,
        database_url=f"sqlite:///{tmp_path / 'persistent-paper.db'}",
        paul_data_dir=str(tmp_path / "data"),
        live_trading=False,
        runtime_auto_start=False,
        runtime_broker="paper",
        simulated_initial_capital_mxn=initial_capital,
    )


def _session_factory(settings: Settings):
    engine = build_engine(settings)
    Base.metadata.create_all(bind=engine)
    return engine, build_session_factory(engine)


def test_persistent_paper_broker_restores_and_closes_the_same_position(tmp_path):
    settings = _settings(tmp_path)
    engine, session_factory = _session_factory(settings)

    broker = PersistentPaperBroker(
        session_factory=session_factory,
        settings=settings,
    )
    broker.connect()
    opened = broker.place_market_buy(
        book="btc_mxn",
        amount_mxn=Decimal("100"),
        price=Decimal("1000"),
    )

    assert opened.status == "filled"
    assert opened.id.startswith("pos_")
    with session_factory() as session:
        repository = SqlSimulatedOrderRepository(session)
        rows = repository.list_open()
        assert [row["id"] for row in rows] == [opened.id]
        assert rows[0]["amount_mxn"] == 100.0
        assert rows[0]["reference_price"] == 1000.0

    restarted = PersistentPaperBroker(
        session_factory=session_factory,
        settings=settings,
    )
    restarted.connect()
    restored_positions = restarted.get_positions()
    assert [position["id"] for position in restored_positions] == [opened.id]
    assert restarted.get_balance().cash_mxn == Decimal("900.0")

    sold = restarted.place_market_sell(
        book="btc_mxn",
        amount_mxn=Decimal("10"),
        price=Decimal("1100"),
    )

    assert sold.status == "filled"
    assert sold.amount_mxn == Decimal("100.0")
    with session_factory() as session:
        repository = SqlSimulatedOrderRepository(session)
        assert repository.list_open() == []
        closed = repository.list_closed()
        assert len(closed) == 1
        assert closed[0]["id"] == opened.id
        assert closed[0]["close_price"] == 1100.0
        assert closed[0]["realized_pnl_mxn"] == 10.0

    final_balance = restarted.get_balance()
    assert final_balance.cash_mxn == Decimal("1010.0")
    assert final_balance.metadata["closed_trades"] == 1
    engine.dispose()


def test_runtime_paper_trade_appears_in_dashboard_positions_and_history(
    tmp_path, fake_bitso
):
    settings = _settings(tmp_path, initial_capital=5000.0)
    application = create_app(settings, fake_bitso)

    with TestClient(application) as client:
        login = client.post("/api/login", json={"password": "test-password"})
        assert login.status_code == 200

        broker = PersistentPaperBroker(
            session_factory=application.state.db_session_factory,
            settings=settings,
        )
        broker.connect()
        opened = broker.place_market_buy(
            book="btc_mxn",
            amount_mxn=Decimal("100"),
            price=Decimal("1000000"),
        )

        positions = client.get("/api/positions")
        assert positions.status_code == 200
        position_payload = positions.json()
        assert position_payload["summary"]["open_positions"] == 1
        assert position_payload["items"][0]["id"] == opened.id
        assert position_payload["items"][0]["book"] == "btc_mxn"

        sold = broker.place_market_sell(
            book="btc_mxn",
            amount_mxn=Decimal("10"),
            price=Decimal("1050000"),
        )
        assert sold.status == "filled"

        positions_after = client.get("/api/positions").json()
        assert positions_after["summary"]["open_positions"] == 0

        history = client.get("/api/simulations?limit=10&offset=0")
        assert history.status_code == 200
        history_payload = history.json()
        assert history_payload["items"][0]["id"] == opened.id
        assert history_payload["items"][0]["status"] == "closed"
        assert history_payload["items"][0]["close_price"] == 1050000.0
        assert history_payload["items"][0]["realized_pnl_mxn"] == 5.0


def test_runtime_route_uses_persistent_paper_broker(tmp_path, fake_bitso):
    settings = _settings(tmp_path)
    application = create_app(settings, fake_bitso)

    with TestClient(application) as client:
        response = client.get("/runtime/status")
        assert response.status_code == 200
        assert response.json()["broker_label"] == "Dinero simulado"
        assert isinstance(
            application.state.runtime_engine.broker,
            PersistentPaperBroker,
        )
        assert runtime_routes._runtime is not None
