import pytest

pytest.importorskip("sqlalchemy")

pytestmark = pytest.mark.database

from datetime import datetime, timezone

from app.repositories.simulated_orders import SqlSimulatedOrderRepository


def add_closed_order(
    client,
    *,
    order_id: str,
    book: str,
    closed_at: datetime,
    amount_mxn: float,
    net_pnl_mxn: float,
    entry_fee_mxn: float = 1.0,
    exit_fee_mxn: float = 1.0,
) -> None:
    session_factory = client.app.state.db_session_factory
    with session_factory() as session:
        repository = SqlSimulatedOrderRepository(session)
        repository.add(
            {
                "id": order_id,
                "created_at": closed_at,
                "closed_at": closed_at,
                "status": "closed",
                "book": book,
                "side": "buy",
                "amount_mxn": amount_mxn,
                "reference_price": 100.0,
                "close_price": 110.0,
                "entry_fee_rate": 0.01,
                "entry_fee_mxn": entry_fee_mxn,
                "exit_fee_rate": 0.01,
                "exit_fee_mxn": exit_fee_mxn,
                "realized_pnl_mxn": net_pnl_mxn,
                "risk_check": "Orden dentro de límites.",
            }
        )
        session.commit()


def test_performance_requires_authentication(client):
    response = client.get("/api/performance")
    assert response.status_code == 401


def test_performance_filters_multiple_books_and_calculates_net_results(client):
    client.post("/api/login", json={"password": "test-password"})
    add_closed_order(
        client,
        order_id="btc-win",
        book="btc_mxn",
        closed_at=datetime(2026, 7, 10, 18, 0, tzinfo=timezone.utc),
        amount_mxn=100,
        net_pnl_mxn=10,
    )
    add_closed_order(
        client,
        order_id="eth-loss",
        book="eth_mxn",
        closed_at=datetime(2026, 7, 11, 18, 0, tzinfo=timezone.utc),
        amount_mxn=200,
        net_pnl_mxn=-5,
    )
    add_closed_order(
        client,
        order_id="sol-excluded",
        book="sol_mxn",
        closed_at=datetime(2026, 7, 12, 18, 0, tzinfo=timezone.utc),
        amount_mxn=100,
        net_pnl_mxn=20,
    )

    response = client.get(
        "/api/performance",
        params={
            "period": "custom",
            "start": "2026-07-01",
            "end": "2026-07-31",
            "books": "btc_mxn,eth_mxn",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["selected_books"] == ["btc_mxn", "eth_mxn"]
    assert data["summary"] == {
        "closed_operations": 2,
        "wins": 1,
        "losses": 1,
        "win_rate_pct": 50.0,
        "invested_mxn": 300.0,
        "gross_pnl_mxn": 9.0,
        "fees_mxn": 4.0,
        "net_pnl_mxn": 5.0,
        "return_pct": 1.6667,
        "best_trade_mxn": 10.0,
        "worst_trade_mxn": -5.0,
        "average_win_mxn": 10.0,
        "average_loss_mxn": -5.0,
    }
    assert [row["book"] for row in data["by_book"]] == ["btc_mxn", "eth_mxn"]
    assert [row["net_pnl_mxn"] for row in data["daily"]] == [10.0, -5.0]
    assert data["daily"][-1]["cumulative_net_pnl_mxn"] == 5.0
    assert [row["id"] for row in data["operations"]] == ["eth-loss", "btc-win"]


def test_performance_rejects_invalid_crypto_and_custom_range(client):
    client.post("/api/login", json={"password": "test-password"})

    invalid_book = client.get("/api/performance?books=not_a_real_market")
    invalid_dates = client.get(
        "/api/performance?period=custom&start=2026-07-20&end=2026-07-01"
    )

    assert invalid_book.status_code == 403
    assert invalid_dates.status_code == 422
