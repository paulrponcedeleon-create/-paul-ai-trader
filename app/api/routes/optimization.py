from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.optimization.engine import OptimizationEngine, OptimizationRequest
from app.optimization.parameter_space import ParameterSpace, ParameterSpaceError
from app.optimization.search import GridSearchOptimizer, RandomSearchOptimizer
from app.repositories.optimizations import OptimizationRepository
from app.services.backtesting import BacktestEngine
from app.services.historical_data import LocalCsvHistoricalDataProvider
from app.strategies.factory import StrategyFactory

router = APIRouter(tags=["optimization"])


class OptimizationBody(BaseModel):
    dataset_id: str
    strategy_name: str
    strategy_version: str = "1.0"
    initial_capital_mxn: float = Field(gt=0)
    trade_amount_mxn: float = Field(gt=0)
    fee_rate: float = Field(ge=0)
    parameter_space: dict[str, list[Any]]
    parameters: dict[str, Any] = Field(default_factory=dict)


class RandomOptimizationBody(OptimizationBody):
    seed: int = 1
    max_iterations: int = Field(gt=0)


@router.post("/optimization/grid")
async def run_grid_optimization(body: OptimizationBody, request: Request):
    return _run(body, request, GridSearchOptimizer().generate)


@router.post("/optimization/random")
async def run_random_optimization(body: RandomOptimizationBody, request: Request):
    optimizer = RandomSearchOptimizer(
        seed=body.seed, max_iterations=body.max_iterations
    )
    return _run(body, request, optimizer.generate)


@router.get("/optimization")
async def list_optimizations(request: Request, limit: int = 100, offset: int = 0):
    with request.app.state.db_session_factory() as session:
        return {
            "items": OptimizationRepository(session).list_runs(
                limit=limit, offset=offset
            )
        }


@router.get("/optimization/{run_id}")
async def get_optimization(run_id: int, request: Request):
    with request.app.state.db_session_factory() as session:
        result = OptimizationRepository(session).get_run_with_results(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Optimización no encontrada.")
        return result


@router.get("/optimization/{run_id}/ranking")
async def get_optimization_ranking(run_id: int, request: Request, top: int = 10):
    with request.app.state.db_session_factory() as session:
        result = OptimizationRepository(session).get_run_with_results(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Optimización no encontrada.")
        ranked = sorted(
            result.get("results", []),
            key=lambda item: item["composite_score"],
            reverse=True,
        )
        return {"items": ranked[:top]}


def _run(body: OptimizationBody, request: Request, generator):
    try:
        parameter_space = ParameterSpace.from_dict(dict(body.parameter_space))
        parameter_space.validate_for_strategy(
            StrategyFactory(), body.strategy_name, body.strategy_version
        )
    except (ParameterSpaceError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=422, detail="Parámetros de optimización inválidos."
        ) from exc
    with request.app.state.db_session_factory() as session:
        provider = LocalCsvHistoricalDataProvider(request.app.state.settings)
        engine = BacktestEngine(
            historical_data_provider=provider, strategy_factory=StrategyFactory()
        )
        report = OptimizationEngine(
            backtest_engine=engine, repository=OptimizationRepository(session)
        ).run(
            OptimizationRequest(
                dataset_id=body.dataset_id,
                strategy_name=body.strategy_name,
                strategy_version=body.strategy_version,
                initial_capital_mxn=body.initial_capital_mxn,
                trade_amount_mxn=body.trade_amount_mxn,
                fee_rate=body.fee_rate,
                parameter_space=parameter_space,
                parameters=body.parameters,
            ),
            generator(parameter_space),
        )
        session.commit()
        if report.status != "completed":
            raise HTTPException(
                status_code=422, detail=report.error or "Optimización inválida."
            )
        return report.to_public_dict()
