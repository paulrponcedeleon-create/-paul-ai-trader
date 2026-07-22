from __future__ import annotations

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")

pytestmark = pytest.mark.database

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.repositories.optimizations import OptimizationRepository


def test_optimization_repository_persists_runs_and_results(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        repo = OptimizationRepository(session)
        run = repo.create_run(
            strategy_name="momentum",
            strategy_version="1.0",
            dataset_id="btc/1d/a.csv",
            parameter_space={"window": [2]},
        )
        repo.add_result(
            run["id"],
            {
                "strategy_name": "momentum",
                "strategy_version": "1.0",
                "parameters": {"window": 2},
                "total_return_pct": 1,
                "max_drawdown_pct": 2,
                "sharpe": 0.5,
                "profit_factor": 1.2,
                "win_rate_pct": 50,
                "trades_count": 1,
                "composite_score": 3,
            },
        )
        repo.update_run(run["id"], status="completed", results_count=1)
        session.commit()
        loaded = repo.get_run_with_results(run["id"])
        assert loaded["status"] == "completed"
        assert loaded["results"][0]["parameters"] == {"window": 2}
