from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")

from app.services.performance_periods import period_bounds, summarize_closed_orders


def _row(book: str, pnl: str, entry_fee: str = "0.10", exit_fee: str = "0.10"):
    return {
        "book": book,
        "realized_pnl_mxn": Decimal(pnl),
        "entry_fee_mxn": Decimal(entry_fee),
        "exit_fee_mxn": Decimal(exit_fee),
    }


def test_period_bounds_use_local_day_week_and_month():
    now = datetime(2026, 7, 24, 6, 30, tzinfo=timezone.utc)
    day_start, _ = period_bounds(now, "day", "America/Chihuahua")
    week_start, _ = period_bounds(now, "week", "America/Chihuahua")
    month_start, _ = period_bounds(now, "month", "America/Chihuahua")

    assert day_start < now
    assert week_start <= day_start
    assert month_start <= week_start
    assert now - day_start < timedelta(days=1)
    assert now - week_start < timedelta(days=7)


def test_summary_uses_decimal_and_counts_wins_losses_flat():
    summary = summarize_closed_orders(
        [
            _row("btc_mxn", "1.005"),
            _row("btc_mxn", "-0.335"),
            _row("eth_mxn", "0.00"),
        ]
    )

    assert summary["realized_pnl_mxn"] == 0.68
    assert summary["fees_mxn"] == 0.60
    assert summary["trades"] == 3
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["flat"] == 1
    assert summary["win_rate_pct"] == 50.0
    assert [item["book"] for item in summary["by_book"]] == [
        "btc_mxn",
        "eth_mxn",
    ]


def test_performance_endpoint_requires_auth(client):
    response = client.get("/api/performance/summary")
    assert response.status_code == 401


def test_performance_endpoint_filters_multiple_books(client):
    assert client.post(
        "/api/login",
        json={"password": "test-password"},
    ).status_code == 200
    response = client.get("/api/performance/summary?books=btc_mxn,eth_mxn")
    assert response.status_code == 200
    payload = response.json()
    assert payload["books"] == ["btc_mxn", "eth_mxn"]
    assert set(payload["periods"]) == {"day", "week", "month"}
    for period in payload["periods"].values():
        assert "realized_pnl_mxn" in period
        assert "fees_mxn" in period
        assert "win_rate_pct" in period
        assert "by_book" in period


def test_performance_endpoint_rejects_invalid_timezone(client):
    assert client.post(
        "/api/login",
        json={"password": "test-password"},
    ).status_code == 200
    response = client.get("/api/performance/summary?timezone=Invalid/Timezone")
    assert response.status_code == 422
    assert response.json() == {"detail": "Zona horaria no válida."}


def test_performance_page_loads_quick_period_cards_asset(client):
    assert client.post(
        "/api/login",
        json={"password": "test-password"},
    ).status_code == 200
    response = client.get("/performance")
    assert response.status_code == 200
    assert "/static/performance-periods.js" in response.text
