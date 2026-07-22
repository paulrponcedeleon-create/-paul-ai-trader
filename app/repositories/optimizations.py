from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import OptimizationResultRow, OptimizationRun
from app.repositories.backtests import dumps_json, loads_json


def _run_to_dict(row: OptimizationRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "strategy_name": row.strategy_name,
        "strategy_version": row.strategy_version,
        "dataset_id": row.dataset_id,
        "parameter_space": loads_json(row.parameter_space_json),
        "status": row.status,
        "results_count": row.results_count,
    }


def _result_to_dict(row: OptimizationResultRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "optimization_run_id": row.optimization_run_id,
        "strategy_name": row.strategy_name,
        "strategy_version": row.strategy_version,
        "parameters": loads_json(row.parameters_json),
        "total_return_pct": row.total_return_pct,
        "max_drawdown_pct": row.max_drawdown_pct,
        "sharpe": row.sharpe,
        "profit_factor": row.profit_factor,
        "win_rate_pct": row.win_rate_pct,
        "trades_count": row.trades_count,
        "composite_score": row.composite_score,
        "metrics": loads_json(row.metrics_json),
    }


class OptimizationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_run(
        self,
        *,
        strategy_name: str,
        strategy_version: str,
        dataset_id: str,
        parameter_space: dict[str, Any],
        status: str = "pending",
    ) -> dict[str, Any]:
        row = OptimizationRun(
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            dataset_id=dataset_id,
            parameter_space_json=dumps_json(parameter_space),
            status=status,
        )
        self.session.add(row)
        self.session.flush()
        return _run_to_dict(row)

    def add_result(
        self, optimization_run_id: int, result: dict[str, Any]
    ) -> dict[str, Any]:
        row = OptimizationResultRow(
            optimization_run_id=optimization_run_id,
            strategy_name=str(result["strategy_name"]),
            strategy_version=str(result["strategy_version"]),
            parameters_json=dumps_json(result.get("parameters", {})),
            total_return_pct=float(result["total_return_pct"]),
            max_drawdown_pct=float(result["max_drawdown_pct"]),
            sharpe=float(result["sharpe"]),
            profit_factor=None
            if result.get("profit_factor") is None
            else float(result["profit_factor"]),
            win_rate_pct=float(result["win_rate_pct"]),
            trades_count=int(result["trades_count"]),
            composite_score=float(result["composite_score"]),
            metrics_json=dumps_json(result),
        )
        self.session.add(row)
        self.session.flush()
        return _result_to_dict(row)

    def update_run(
        self, run_id: int, *, status: str, results_count: int
    ) -> dict[str, Any] | None:
        row = self.session.get(OptimizationRun, run_id)
        if row is None:
            return None
        row.status = status
        row.results_count = results_count
        self.session.flush()
        return _run_to_dict(row)

    def list_runs(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(OptimizationRun)
            .order_by(OptimizationRun.created_at.desc(), OptimizationRun.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return [_run_to_dict(row) for row in rows]

    def get_run_with_results(self, run_id: int) -> dict[str, Any] | None:
        row = self.session.scalars(
            select(OptimizationRun)
            .options(selectinload(OptimizationRun.results))
            .where(OptimizationRun.id == run_id)
        ).first()
        if row is None:
            return None
        data = _run_to_dict(row)
        data["results"] = [_result_to_dict(result) for result in row.results]
        return data
