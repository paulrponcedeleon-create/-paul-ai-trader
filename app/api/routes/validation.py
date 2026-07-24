from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.dependencies import require_auth
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
    user_id = require_auth(request)
    _load_sources_if_available(request, user_id)
    payload = _manager(request, user_id).status()
    payload["user_id"] = user_id
    payload["learning_sources"] = _learning_summaries(request).get(
        user_id,
        learning_source_summary([]),
    )
    return payload


@router.get("/validation/promotions")
async def validation_promotions(request: Request):
    user_id = require_auth(request)
    _load_sources_if_available(request, user_id)
    return _manager(request, user_id).promotions()


@router.get("/validation/retirements")
async def validation_retirements(request: Request):
    user_id = require_auth(request)
    _load_sources_if_available(request, user_id)
    return _manager(request, user_id).retirements()


@router.get("/validation/report")
async def validation_report(request: Request, format: str = "json"):
    user_id = require_auth(request)
    _load_sources_if_available(request, user_id)
    data = _manager(request, user_id).report()
    data["user_id"] = user_id
    data["learning_sources"] = _learning_summaries(request).get(
        user_id,
        learning_source_summary([]),
    )
    if format == "csv":
        return {"format": "csv", "content": export_validation_csv(data)}
    if format == "markdown":
        return {"format": "markdown", "content": export_validation_markdown(data)}
    if format == "html":
        return {"format": "html", "content": export_validation_html(data)}
    return {"format": "json", "content": export_validation_json(data)}


def _managers(request: Request) -> dict[str, ValidationManager]:
    managers = getattr(request.app.state, "validation_managers", None)
    if managers is None:
        managers = {}
        request.app.state.validation_managers = managers
    return managers


def _learning_summaries(request: Request) -> dict[str, dict]:
    summaries = getattr(request.app.state, "learning_source_summaries", None)
    if summaries is None:
        summaries = {}
        request.app.state.learning_source_summaries = summaries
    return summaries


def _learning_signatures(request: Request) -> dict[str, tuple[int, int, int]]:
    signatures = getattr(request.app.state, "validation_learning_signatures", None)
    if signatures is None:
        signatures = {}
        request.app.state.validation_learning_signatures = signatures
    return signatures


def _manager(request: Request, user_id: str) -> ValidationManager:
    managers = _managers(request)
    manager = managers.get(user_id)
    if manager is None:
        manager = ValidationManager()
        managers[user_id] = manager
    return manager


def _load_sources_if_available(request: Request, user_id: str) -> None:
    manager = _manager(request, user_id)
    observations: list[dict] = []
    summary = learning_source_summary([])

    try:
        with request.app.state.db_session_factory() as session:
            rows = SqlSimulatedOrderRepository(session, user_id=user_id).list(limit=10000)
        observations = build_learning_observations(rows)
        summary = learning_source_summary(rows)
        _learning_summaries(request)[user_id] = summary
    except Exception:
        _learning_summaries(request)[user_id] = summary

    signature = (
        summary["manual_samples"],
        summary["runtime_samples"],
        summary["exploration_samples"],
    )
    signatures = _learning_signatures(request)
    if manager.current_run is not None and signatures.get(user_id) == signature:
        return

    if not observations:
        signatures[user_id] = signature
        return

    research = getattr(request.app.state, "research_manager", None)
    research_run = getattr(research, "current_run", None)
    manager.run(research_run=research_run, paper_observations=observations)
    signatures[user_id] = signature
