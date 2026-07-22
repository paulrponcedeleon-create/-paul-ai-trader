from __future__ import annotations

from fastapi import APIRouter, Request

from app.reporting.validation_reports import (
    export_validation_csv,
    export_validation_html,
    export_validation_json,
    export_validation_markdown,
)
from app.validation import ValidationManager

router = APIRouter(tags=["validation"])


@router.get("/validation/status")
async def validation_status(request: Request):
    _load_sources_if_available(request)
    return _manager(request).status()


@router.get("/validation/promotions")
async def validation_promotions(request: Request):
    _load_sources_if_available(request)
    return _manager(request).promotions()


@router.get("/validation/retirements")
async def validation_retirements(request: Request):
    _load_sources_if_available(request)
    return _manager(request).retirements()


@router.get("/validation/report")
async def validation_report(request: Request, format: str = "json"):
    _load_sources_if_available(request)
    data = _manager(request).report()
    if format == "csv":
        return {"format": "csv", "content": export_validation_csv(data)}
    if format == "markdown":
        return {"format": "markdown", "content": export_validation_markdown(data)}
    if format == "html":
        return {"format": "html", "content": export_validation_html(data)}
    return {"format": "json", "content": export_validation_json(data)}


def _manager(request: Request) -> ValidationManager:
    manager = getattr(request.app.state, "validation_manager", None)
    if manager is None:
        manager = ValidationManager()
        request.app.state.validation_manager = manager
    return manager


def _load_sources_if_available(request: Request) -> None:
    manager = _manager(request)
    if manager.current_run is not None:
        return
    research = getattr(request.app.state, "research_manager", None)
    research_run = getattr(research, "current_run", None)
    observations = getattr(request.app.state, "paper_performance_observations", None)
    if research_run is not None or observations:
        manager.run(research_run=research_run, paper_observations=observations)
