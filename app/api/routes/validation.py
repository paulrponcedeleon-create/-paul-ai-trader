from __future__ import annotations

from fastapi import APIRouter, Request

from app.reporting.validation_reports import (
    export_validation_csv,
    export_validation_html,
    export_validation_json,
    export_validation_markdown,
)
from app.repositories.simulated_orders import SqlSimulatedOrderRepository
from app.services.learning_observations import (
    build_learning_observations,
    learning_source_summary,
)
from app.validation import ValidationManager

router = APIRouter(tags=["validation"])


@router.get("/validation/status")
async def validation_status(request: Request):
    _load_sources_if_available(request)
    payload = _manager(request).status()
    payload["learning_sources"] = getattr(
        request.app.state,
        "learning_source_summary",
        learning_source_summary([]),
    )
    return payload


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
    data["learning_sources"] = getattr(
        request.app.state,
        "learning_source_summary",
        learning_source_summary([]),
    )
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
    observations: list[dict] = []
    summary = learning_source_summary([])

    try:
        with request.app.state.db_session_factory() as session:
            rows = SqlSimulatedOrderRepository(session).list(limit=10000)
        observations = build_learning_observations(rows)
        summary = learning_source_summary(rows)
        request.app.state.paper_performance_observations = observations
        request.app.state.learning_source_summary = summary
    except Exception:
        request.app.state.learning_source_summary = summary

    signature = (
        summary["manual_samples"],
        summary["runtime_samples"],
        summary["exploration_samples"],
    )
    if (
        manager.current_run is not None
        and getattr(request.app.state, "validation_learning_signature", None)
        == signature
    ):
        return

    # Research can provide an expected baseline, but it must never create fake
    # paper results. Validation only runs after at least one position is closed.
    if not observations:
        request.app.state.validation_learning_signature = signature
        return

    research = getattr(request.app.state, "research_manager", None)
    research_run = getattr(research, "current_run", None)
    manager.run(research_run=research_run, paper_observations=observations)
    request.app.state.validation_learning_signature = signature
