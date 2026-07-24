from datetime import datetime, timezone
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")
pytestmark = pytest.mark.database

from app.repositories.simulated_orders import SqlSimulatedOrderRepository


def _open_position(repository: SqlSimulatedOrderRepository) -> None:
    repository.add(
        {
            "id": "btc-lot-1",
            "created_at": datetime.now(timezone.utc),
            "status": "open",
            "book": "btc_mxn",
            "side": "buy",
            "amount_mxn": Decimal("100.00"),
            "reference_price": Decimal("1000.00"),
            "entry_fee_rate": Decimal("0.010000000000"),
            "entry_fee_mxn": Decimal("1.00"),
            "risk_check": "test",
        }
    )


def test_partial_close_splits_cost_and_entry_fee_exactly(client):
    session_factory = client.app.state.db_session_factory
    with session_factory() as session:
        repository = SqlSimulatedOrderRepository(session)
        _open_position(repository)
        session.commit()

        result = repository.close_partial(
            "btc-lot-1",
            closed_lot_id="btc-lot-1-sell-1",
            amount_mxn=Decimal("30.00"),
            closed_at=datetime.now(timezone.utc),
            close_price=Decimal("1100.00"),
            exit_fee_rate=Decimal("0.010000000000"),
            exit_fee_mxn=Decimal("0.33"),
            realized_pnl_mxn=Decimal("2.37"),
        )
        assert result is not None
        closed, remaining = result
        session.commit()

    assert closed["amount_mxn"] == 30.0
    assert closed["entry_fee_mxn"] == 0.3
    assert closed["parent_position_id"] == "btc-lot-1"
    assert remaining["amount_mxn"] == 70.0
    assert remaining["entry_fee_mxn"] == 0.7
    assert remaining["status"] == "open"


def test_two_partial_closes_preserve_original_principal(client):
    session_factory = client.app.state.db_session_factory
    with session_factory() as session:
        repository = SqlSimulatedOrderRepository(session)
        _open_position(repository)
        session.commit()

        first = repository.close_partial(
            "btc-lot-1",
            closed_lot_id="btc-lot-1-sell-1",
            amount_mxn=Decimal("30.00"),
            closed_at=datetime.now(timezone.utc),
            close_price=Decimal("1100.00"),
            exit_fee_rate=Decimal("0"),
            exit_fee_mxn=Decimal("0"),
            realized_pnl_mxn=Decimal("3.00"),
        )
        second = repository.close_partial(
            "btc-lot-1",
            closed_lot_id="btc-lot-1-sell-2",
            amount_mxn=Decimal("20.00"),
            closed_at=datetime.now(timezone.utc),
            close_price=Decimal("900.00"),
            exit_fee_rate=Decimal("0"),
            exit_fee_mxn=Decimal("0"),
            realized_pnl_mxn=Decimal("-2.00"),
        )
        assert first is not None and second is not None
        final = repository.close(
            "btc-lot-1",
            closed_at=datetime.now(timezone.utc),
            close_price=Decimal("1000.00"),
            exit_fee_rate=Decimal("0"),
            exit_fee_mxn=Decimal("0"),
            realized_pnl_mxn=Decimal("0"),
        )
        session.commit()

        rows = repository.list()
        ledger = repository.capital_ledger_decimal(Decimal("1000.00"))

    assert final is not None
    assert sum(Decimal(str(row["amount_mxn"])) for row in rows) == Decimal("100.00")
    assert sum(
        Decimal(str(row["entry_fee_mxn"] or 0)) for row in rows
    ) == Decimal("1.00")
    assert ledger["open_invested_mxn"] == Decimal("0.00")
    assert ledger["realized_pnl_mxn"] == Decimal("1.00")
    assert ledger["available_cash_mxn"] == Decimal("1001.00")


def test_partial_close_rejects_zero_or_full_amount(client):
    session_factory = client.app.state.db_session_factory
    with session_factory() as session:
        repository = SqlSimulatedOrderRepository(session)
        _open_position(repository)
        session.commit()

        with pytest.raises(ValueError):
            repository.close_partial(
                "btc-lot-1",
                closed_lot_id="invalid-full",
                amount_mxn=Decimal("100.00"),
                closed_at=datetime.now(timezone.utc),
                close_price=Decimal("1000"),
                exit_fee_rate=Decimal("0"),
                exit_fee_mxn=Decimal("0"),
                realized_pnl_mxn=Decimal("0"),
            )
