from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

from app.experiments import Experiment, ExperimentManager
from app.reporting.experiment_reports import (
    export_experiment_csv,
    export_experiment_html,
    export_experiment_json,
    export_experiment_markdown,
)
from app.services.historical_data import LocalCsvHistoricalDataProvider

router = APIRouter(tags=["experiments"])


@router.post("/experiments")
async def create_experiment(request: Request, payload: dict[str, Any] = Body(...)):
    try:
        experiment = _experiment_from_payload(payload)
        return _manager(request).create(experiment).to_public_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/experiments/run")
async def run_experiment(
    request: Request,
    experiment_id: str = Query(...),
    mode: str = Query(
        "backtest", pattern="^(backtest|walk_forward|optimization|paper_replay)$"
    ),
):
    try:
        return _manager(request).run(experiment_id, mode).to_public_dict()  # type: ignore[arg-type]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/experiments")
async def list_experiments(request: Request):
    return [item.to_public_dict() for item in _manager(request).list()]


@router.get("/experiments/compare")
async def compare_experiments(request: Request, ids: str | None = None):
    experiment_ids = tuple(item.strip() for item in ids.split(",")) if ids else None
    return _manager(request).compare(experiment_ids).to_public_dict()


@router.get("/experiments/report")
async def experiment_report(
    request: Request, format: str = "json", ids: str | None = None
):
    experiment_ids = tuple(item.strip() for item in ids.split(",")) if ids else None
    comparison = _manager(request).compare(experiment_ids)
    if format == "csv":
        return {"format": "csv", "content": export_experiment_csv(comparison)}
    if format == "markdown":
        return {"format": "markdown", "content": export_experiment_markdown(comparison)}
    if format == "html":
        return {"format": "html", "content": export_experiment_html(comparison)}
    return {"format": "json", "content": export_experiment_json(comparison)}


@router.get("/experiments/{experiment_id}")
async def get_experiment(request: Request, experiment_id: str):
    experiment = _manager(request).get(experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experimento no encontrado.")
    return experiment.to_public_dict()


def _manager(request: Request) -> ExperimentManager:
    manager = getattr(request.app.state, "experiment_manager", None)
    if manager is None:
        settings = request.app.state.settings
        manager = ExperimentManager(
            historical_data_provider=LocalCsvHistoricalDataProvider(settings)
        )
        request.app.state.experiment_manager = manager
    return manager


def _experiment_from_payload(payload: dict[str, Any]) -> Experiment:
    parameter_space = payload.get("parameter_space") or {}
    return Experiment(
        name=str(payload.get("name", "")),
        description=str(payload.get("description", "")),
        strategy_name=str(payload.get("strategy_name", payload.get("strategy", ""))),
        strategy_version=str(payload.get("strategy_version", "1.0")),
        parameters=dict(payload.get("parameters", {})),
        assets=tuple(payload.get("assets", [])),
        timeframe=str(payload.get("timeframe", "1m")),
        initial_capital_mxn=Decimal(str(payload.get("initial_capital_mxn", 10000))),
        trade_amount_mxn=Decimal(str(payload.get("trade_amount_mxn", 1000))),
        fee_rate=Decimal(str(payload.get("fee_rate", 0.001))),
        start_at=_parse_datetime(payload.get("start_at")),
        end_at=_parse_datetime(payload.get("end_at")),
        risk_config=dict(payload.get("risk_config", {})),
        version=str(payload.get("version", "1.0")),
        dataset_id=payload.get("dataset_id"),
        parameter_space={key: tuple(value) for key, value in parameter_space.items()},
    )


def _parse_datetime(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
