from datetime import datetime, timezone
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")

from app.repositories.simulated_orders import SqlSimulatedOrderRepository
from app.services.learning_observations import (
    build_learning_observations,
    learning_source_summary,
)
from app.services.performance_periods import summarize_closed_orders
from app.services.trade_sources import infer_position_source


def _order(
    order_id: str,
    *,
    source: str,
    status: str = "open",
    pnl: str | None = None,
    risk_check: str = "risk_ok",
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": order_id,
        "created_at": now,
        "closed_at": now if status == "closed" else None,
        "status": status,
        "source": source,
        "book": "btc_mxn",
        "side": "buy",
        "amount_mxn": Decimal("100.00"),
        "reference_price": Decimal("1000.00"),
        "close_price": Decimal("1010.00") if status == "closed" else None,
        "entry_fee_rate": Decimal("0"),
        "entry_fee_mxn": Decimal("0"),
        "exit_fee_rate": Decimal("0") if status == "closed" else None,
        "exit_fee_mxn": Decimal("0") if status == "closed" else None,
        "realized_pnl_mxn": Decimal(pnl) if pnl is not None else None,
        "risk_check": risk_check,
    }


def test_source_inference_distinguishes_manual_runtime_and_exploration():
    assert infer_position_source({"risk_check": "manual risk accepted"}) == "manual"
    assert infer_position_source({"risk_check": "strategy_buy"}) == "runtime"
    assert (
        infer_position_source({"risk_check": "paper_exploration_hold_streak"})
        == "exploration"
    )
    assert infer_position_source({"source": "runtime", "risk_check": "anything"}) == "runtime"


def test_learning_summary_tracks_open_but_learns_only_from_closed():
    rows = [
        _order("manual-open", source="manual"),
        _order("runtime-closed", source="runtime", status="closed", pnl="5.00"),
        _order(
            "exploration-closed",
            source="exploration",
            status="closed",
            pnl="-2.00",
        ),
    ]

    summary = learning_source_summary(rows)
    observations = build_learning_observations(rows)

    assert summary["active_tracking_samples"] == 1
    assert summary["completed_result_samples"] == 2
    assert summary["manual_samples"] == 0
    assert summary["runtime_samples"] == 1
    assert summary["exploration_samples"] == 1
    assert {item["source"] for item in observations} == {"runtime", "exploration"}


def test_performance_compares_manual_against_bot_and_ai_without_mixing():
    summary = summarize_closed_orders(
        [
            _order("manual", source="manual", status="closed", pnl="3.00"),
            _order("runtime", source="runtime", status="closed", pnl="4.00"),
            _order("exploration", source="exploration", status="closed", pnl="-1.00"),
        ]
    )

    assert summary["comparison"]["manual"]["trades"] == 1
    assert summary["comparison"]["manual"]["realized_pnl_mxn"] == 3.0
    assert summary["comparison"]["bot"]["trades"] == 2
    assert summary["comparison"]["bot"]["realized_pnl_mxn"] == 3.0
    assert {item["source"] for item in summary["by_source"]} == {
        "manual",
        "runtime",
        "exploration",
    }


def test_positions_api_returns_persistent_source_and_source_summary(client):
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200

    with client.app.state.db_session_factory() as session:
        repository = SqlSimulatedOrderRepository(session)
        repository.add(_order("manual-position", source="manual"))
        repository.add(
            _order(
                "runtime-position",
                source="runtime",
                risk_check="strategy_buy",
            )
        )
        repository.add(
            _order(
                "exploration-position",
                source="exploration",
                risk_check="paper_exploration_hold_streak",
            )
        )
        session.commit()

    response = client.get("/api/positions")
    assert response.status_code == 200
    payload = response.json()
    assert {item["source"] for item in payload["items"]} == {
        "manual",
        "runtime",
        "exploration",
    }
    assert payload["summary"]["source_counts"] == {
        "manual": 1,
        "runtime": 1,
        "exploration": 1,
    }


def test_validation_status_uses_real_open_and_closed_positions(client):
    with client.app.state.db_session_factory() as session:
        repository = SqlSimulatedOrderRepository(session)
        repository.add(_order("manual-open", source="manual"))
        repository.add(
            _order("runtime-closed", source="runtime", status="closed", pnl="2.50")
        )
        session.commit()

    response = client.get("/validation/status")
    assert response.status_code == 200
    learning = response.json()["learning_sources"]
    assert learning["active_tracking_samples"] == 1
    assert learning["completed_result_samples"] == 1
    assert learning["comparison"]["manual"]["open_positions"] == 1
    assert learning["comparison"]["bot"]["closed_positions"] == 1


def test_dashboard_assets_explain_real_source_metrics(client):
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200
    page = client.get("/")
    script = client.get("/static/dashboard-v2.js")
    source_script = client.get("/static/source-attribution.js")

    assert page.status_code == 200
    assert "MANUAL VS BOT VS IA" in page.text
    assert "/static/source-attribution.js" in page.text
    assert "Operaciones cerradas aprendidas" in script.text
    assert "P&L flotante" in script.text
    assert "Manual · Paul" in source_script.text
    assert "IA exploratoria" in source_script.text
