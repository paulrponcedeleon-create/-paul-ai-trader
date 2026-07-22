from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request

from app.experiments import ExperimentManager
from app.reporting.research_reports import (
    export_research_csv,
    export_research_html,
    export_research_json,
    export_research_markdown,
)
from app.research import ResearchManager
from app.services.historical_data import LocalCsvHistoricalDataProvider

router = APIRouter(tags=["research"])


@router.post("/research/start")
async def research_start(request: Request, payload: dict[str, Any] = Body(...)):
    return _manager(request).start(payload).to_public_dict()


@router.get("/research/status")
async def research_status(request: Request):
    return _manager(request).status()


@router.get("/research/results")
async def research_results(request: Request):
    return _manager(request).results()


@router.get("/research/report")
async def research_report(request: Request, format: str = "json"):
    run = _manager(request).current_run
    data = run.to_public_dict() if run else {"results": [], "ranking": []}
    if format == "csv":
        return {"format": "csv", "content": export_research_csv(data)}
    if format == "markdown":
        return {"format": "markdown", "content": export_research_markdown(data)}
    if format == "html":
        return {"format": "html", "content": export_research_html(data)}
    return {"format": "json", "content": export_research_json(data)}


def _manager(request: Request) -> ResearchManager:
    manager = getattr(request.app.state, "research_manager", None)
    if manager is None:
        experiment_manager = getattr(request.app.state, "experiment_manager", None)
        if experiment_manager is None:
            settings = request.app.state.settings
            experiment_manager = ExperimentManager(
                historical_data_provider=LocalCsvHistoricalDataProvider(settings)
            )
            request.app.state.experiment_manager = experiment_manager
        manager = ResearchManager(experiment_manager)
        request.app.state.research_manager = manager
    return manager
