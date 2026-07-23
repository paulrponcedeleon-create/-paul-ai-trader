from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import Numeric, select

from app.db.models import SimulatedOrder
from app.db.order_models import SimulatedOrderEvent
from app.repositories.order_events import SqlSimulatedOrderEventRepository
from app.repositories.simulated_orders import SqlSimulatedOrderRepository
from app.services.money import quantize_money, to_decimal

pytestmark = pytest.mark.database


def _open_position(repository, *, position_id: str, amount: str) -> None:
    repository.add(
        {
            "id": position_id,
            "created_at": datetime.now(timezone.utc),
            "status": "open",
            "book": "btc_mxn",
            "side": "buy",
            "amount_mxn": Decimal(amount),
            "reference_price": Decimal("100.123456789012"),
            "entry_fee_rate": Decimal("0.000000000000"),
            "entry_fee_mxn": Decimal("0.00"),
            "risk_check": "decimal_test",
        }
    )


def test_money_rounding_neutralizes_binary_float_artifacts():
    assert to_decimal(0.1 + 0.2) == Decimal("0.30000000000000004")
    assert quantize_money(0.1 + 0.2) == Decimal("0.30")
    assert quantize_money("1.005") == Decimal("1.01")


def test_simulated_models_use_numeric_decimal_columns():
    assert isinstance(SimulatedOrder.__table__.c.amount_mxn.type, Numeric)
    assert isinstance(SimulatedOrder.__table__.c.reference_price.type, Numeric)
    assert isinstance(SimulatedOrder.__table__.c.realized_pnl_mxn.type, Numeric)
    assert isinstance(SimulatedOrderEvent.__table__.c.amount_mxn.type, Numeric)
    assert isinstance(SimulatedOrderEvent.__table__.c.fee_mxn.type, Numeric)


def test_capital_ledger_stays_exact_through_open_and_close(client):
    session_factory = client.app.state.db_session_factory
    with session_factory() as session:
        repository = SqlSimulatedOrderRepository(session)
        _open_position(repository, position_id="decimal-010", amount="0.10")
        _open_position(repository, position_id="decimal-020", amount="0.20")
        session.commit()

        before = repository.capital_ledger_decimal(Decimal("1.00"))
        assert before == {
            "initial_capital_mxn": Decimal("1.00"),
            "open_invested_mxn": Decimal("0.30"),
            "realized_pnl_mxn": Decimal("0.00"),
            "available_cash_mxn": Decimal("0.70"),
            "account_equity_before_unrealized_mxn": Decimal("1.00"),
        }

        repository.close(
            "decimal-010",
            closed_at=datetime.now(timezone.utc),
            close_price=Decimal("101.123456789012"),
            exit_fee_rate=Decimal("0.000000000000"),
            exit_fee_mxn=Decimal("0.00"),
            realized_pnl_mxn=Decimal("0.10"),
        )
        session.commit()

        after = repository.capital_ledger_decimal(Decimal("1.00"))
        assert after["open_invested_mxn"] == Decimal("0.20")
        assert after["realized_pnl_mxn"] == Decimal("0.10")
        assert after["available_cash_mxn"] == Decimal("0.90")
        assert after["account_equity_before_unrealized_mxn"] == Decimal("1.10")

        stored = session.get(SimulatedOrder, "decimal-010")
        assert isinstance(stored.amount_mxn, Decimal)
        assert stored.amount_mxn == Decimal("0.10")
        assert stored.realized_pnl_mxn == Decimal("0.10")


def test_order_event_repository_rounds_once_and_stores_decimal(client):
    session_factory = client.app.state.db_session_factory
    with session_factory() as session:
        repository = SqlSimulatedOrderEventRepository(session)
        payload = repository.add(
            {
                "id": "evt_decimal_exact",
                "created_at": datetime.now(timezone.utc),
                "position_id": "decimal-position",
                "book": "btc_mxn",
                "side": "buy",
                "status": "filled",
                "amount_mxn": Decimal("10.005"),
                "price": Decimal("123.1234567890124"),
                "fee_mxn": Decimal("0.005"),
                "source": "manual",
                "reason": "decimal_test",
            }
        )
        session.commit()

        stored = session.scalar(
            select(SimulatedOrderEvent).where(
                SimulatedOrderEvent.id == "evt_decimal_exact"
            )
        )
        assert isinstance(stored.amount_mxn, Decimal)
        assert stored.amount_mxn == Decimal("10.01")
        assert stored.price == Decimal("123.123456789012")
        assert stored.fee_mxn == Decimal("0.01")
        assert payload["amount_mxn"] == 10.01
        assert payload["fee_mxn"] == 0.01
