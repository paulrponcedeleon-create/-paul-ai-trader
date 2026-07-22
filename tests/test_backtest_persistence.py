from datetime import datetime, timezone

import pytest

pytest.importorskip("sqlalchemy")

pytestmark = pytest.mark.database
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.repositories.backtests import BacktestRepository


def repo_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'backtests.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    return factory()


def test_backtest_repository_run_trade_and_results(tmp_path):
    with repo_session(tmp_path) as session:
        repo = BacktestRepository(session)
        run = repo.create_run(
            strategy_name="momentum",
            strategy_version="v1",
            book="BTC_MXN",
            start_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            end_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
            initial_capital_mxn=1000,
            parameters={"b": 1, "a": 2},
        )
        assert run["parameters"] == {"a": 2, "b": 1}
        trade = repo.add_trade(
            backtest_run_id=run["id"],
            opened_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            closed_at=datetime(2026, 7, 1, 1, tzinfo=timezone.utc),
            book="BTC_MXN",
            side="buy",
            entry_price=100,
            exit_price=110,
            amount_mxn=500,
            pnl_mxn=50,
            return_pct=10,
            fees_mxn=7.8,
            signal={"action": "buy"},
        )
        assert trade["book"] == "btc_mxn"
        updated = repo.update_run_results(
            run["id"],
            final_capital_mxn=1050,
            total_return_pct=5,
            max_drawdown_pct=2,
            win_rate_pct=100,
            trades_count=1,
            metrics={"fees_total": 7.8},
        )
        assert updated["status"] == "completed"
        with_trades = repo.get_run_with_trades(run["id"])
        assert with_trades["trades"][0]["signal"] == {"action": "buy"}
        assert repo.list_trades(run["id"])[0]["id"] == trade["id"]


def test_backtest_repository_rejects_non_serializable_json(tmp_path):
    with repo_session(tmp_path) as session:
        repo = BacktestRepository(session)
        with pytest.raises(ValueError, match="JSON no serializable"):
            repo.create_run(
                strategy_name="momentum",
                strategy_version="v1",
                book="btc_mxn",
                start_at=None,
                end_at=None,
                initial_capital_mxn=1000,
                parameters={"bad": {1, 2}},
            )


def test_backtest_repository_rejects_invalid_stored_json(tmp_path):
    with repo_session(tmp_path) as session:
        repo = BacktestRepository(session)
        run = repo.create_run(
            strategy_name="momentum",
            strategy_version="v1",
            book="btc_mxn",
            start_at=None,
            end_at=None,
            initial_capital_mxn=1000,
        )
        from app.db.models import BacktestRun

        row = session.get(BacktestRun, run["id"])
        row.metrics_json = "[1, 2]"
        session.flush()
        with pytest.raises(ValueError, match="JSON almacenado inválido"):
            repo.get_run(run["id"])
