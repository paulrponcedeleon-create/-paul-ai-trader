from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.repositories.backtests import BacktestRepository
from app.services.backtesting import BacktestEngine, BacktestRequest
from app.services.historical_data import LocalCsvHistoricalDataProvider
from app.services.walk_forward import WalkForwardEngine, WalkForwardRequest
from app.strategies.factory import StrategyFactory
from app.strategies.registry import strategy_registry

router = APIRouter(tags=["strategy-platform"])


class BacktestRunRequest(BaseModel):
    dataset_id: str
    strategy_name: str
    strategy_version: str = "1.0"
    initial_capital_mxn: float = Field(gt=0)
    trade_amount_mxn: float = Field(gt=0)
    fee_rate: float = Field(ge=0)
    start_at: datetime | None = None
    end_at: datetime | None = None
    parameters: dict = Field(default_factory=dict)


class WalkForwardRunRequest(BacktestRunRequest):
    training_window_days: int = Field(gt=0)
    validation_window_days: int = Field(gt=0)
    mode: str = "rolling"


@router.get("/strategies")
async def list_strategies():
    return {"items": strategy_registry.list()}


@router.get("/strategies/{name}")
async def get_strategy(name: str, version: str | None = None):
    try:
        strategy_cls = strategy_registry.get(name, version)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="Estrategia no encontrada."
        ) from exc
    return {
        "name": strategy_cls.name,
        "version": strategy_cls.version,
        "description": strategy_cls.description,
        "parameters_schema": strategy_cls.parameters_schema(),
    }


@router.post("/backtests")
async def create_backtest(body: BacktestRunRequest, request: Request):
    with request.app.state.db_session_factory() as session:
        engine = _engine(request, BacktestRepository(session))
        result = engine.run(BacktestRequest(**body.model_dump()))
        if result.status == "completed":
            session.commit()
            return result.to_public_dict()
        session.commit()
        raise HTTPException(
            status_code=422, detail=result.error or "Backtest inválido."
        )


@router.get("/backtests")
async def list_backtests(request: Request, limit: int = 100, offset: int = 0):
    with request.app.state.db_session_factory() as session:
        return {
            "items": BacktestRepository(session).list_runs(limit=limit, offset=offset)
        }


@router.get("/backtests/{run_id}")
async def get_backtest(run_id: int, request: Request):
    with request.app.state.db_session_factory() as session:
        result = BacktestRepository(session).get_run_with_trades(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Backtest no encontrado.")
        return result


@router.delete("/backtests/{run_id}")
async def delete_backtest(run_id: int, request: Request):
    with request.app.state.db_session_factory() as session:
        deleted = BacktestRepository(session).delete_run(run_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Backtest no encontrado.")
        session.commit()
        return {"deleted": True}


@router.post("/walk-forward")
async def run_walk_forward(body: WalkForwardRunRequest, request: Request):
    if body.start_at is None or body.end_at is None:
        raise HTTPException(status_code=422, detail="start_at y end_at son requeridos.")
    with request.app.state.db_session_factory() as session:
        report = WalkForwardEngine(_engine(request, BacktestRepository(session))).run(
            WalkForwardRequest(
                dataset_id=body.dataset_id,
                strategy_name=body.strategy_name,
                strategy_version=body.strategy_version,
                initial_capital_mxn=body.initial_capital_mxn,
                trade_amount_mxn=body.trade_amount_mxn,
                fee_rate=body.fee_rate,
                training_window_days=body.training_window_days,
                validation_window_days=body.validation_window_days,
                start_at=body.start_at,
                end_at=body.end_at,
                mode="anchored" if body.mode == "anchored" else "rolling",
                parameters=body.parameters,
            )
        )
        session.commit()
    return {
        "mode": report.mode,
        "consolidated": report.consolidated,
        "segments": [
            {
                "training_start": segment.training_start.isoformat(),
                "training_end": segment.training_end.isoformat(),
                "validation_start": segment.validation_start.isoformat(),
                "validation_end": segment.validation_end.isoformat(),
                "result": segment.result.to_public_dict(),
            }
            for segment in report.segments
        ],
    }


def _engine(
    request: Request, repository: BacktestRepository | None = None
) -> BacktestEngine:
    provider = LocalCsvHistoricalDataProvider(request.app.state.settings)
    return BacktestEngine(
        historical_data_provider=provider,
        repository=repository,
        strategy_factory=StrategyFactory(),
    )
