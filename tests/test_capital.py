import pytest

pytest.importorskip("sqlalchemy")

pytestmark = pytest.mark.database

from datetime import datetime, timezone

from app.repositories.simulated_orders import SqlSimulatedOrderRepository


def test_capital_endpoint_and_order_balance(client):
    client.post("/api/login", json={"password": "test-password"})

    capital = client.get("/api/capital")
    assert capital.status_code == 200
    assert capital.json()["available_cash_mxn"] == 5000.0

    session_factory = client.app.state.db_session_factory
    with session_factory() as session:
        repository = SqlSimulatedOrderRepository(session)
        repository.add(
            {
                "id": "large-open-position",
                "created_at": datetime.now(timezone.utc),
                "status": "open",
                "book": "btc_mxn",
                "side": "buy",
                "amount_mxn": 4900.0,
                "reference_price": 100.0,
                "entry_fee_rate": 0.0,
                "entry_fee_mxn": 0.0,
                "risk_check": "ok",
            }
        )
        session.commit()

    capital_after = client.get("/api/capital").json()
    assert capital_after["available_cash_mxn"] == 100.0
    assert capital_after["open_invested_mxn"] == 4900.0

    blocked = client.post(
        "/api/orders",
        json={"book": "eth_mxn", "side": "buy", "amount_mxn": 200},
    )
    assert blocked.status_code == 403
    assert "Saldo insuficiente" in blocked.json()["detail"]


def test_simulated_spot_rejects_new_sell_orders(client):
    client.post("/api/login", json={"password": "test-password"})
    response = client.post(
        "/api/orders",
        json={"book": "btc_mxn", "side": "sell", "amount_mxn": 100},
    )
    assert response.status_code == 403
    assert "no puedes vender un activo que no tienes" in response.json()["detail"]


def test_closed_result_returns_principal_and_applies_realized_pnl(client):
    session_factory = client.app.state.db_session_factory
    with session_factory() as session:
        repository = SqlSimulatedOrderRepository(session)
        repository.add(
            {
                "id": "capital-close",
                "created_at": datetime.now(timezone.utc),
                "status": "open",
                "book": "btc_mxn",
                "side": "buy",
                "amount_mxn": 100.0,
                "reference_price": 100.0,
                "entry_fee_rate": 0.0,
                "entry_fee_mxn": 0.0,
                "risk_check": "ok",
            }
        )
        session.commit()
        before = repository.capital_ledger(1000.0)
        assert before["available_cash_mxn"] == 900.0
        repository.close(
            "capital-close",
            closed_at=datetime.now(timezone.utc),
            close_price=110.0,
            exit_fee_rate=0.0,
            exit_fee_mxn=0.0,
            realized_pnl_mxn=10.0,
        )
        session.commit()
        after = repository.capital_ledger(1000.0)

    assert after["available_cash_mxn"] == 1010.0
    assert after["realized_pnl_mxn"] == 10.0
