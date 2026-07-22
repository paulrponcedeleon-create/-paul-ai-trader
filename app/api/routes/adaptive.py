from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.adaptive import AdaptiveManager
from app.reporting.adaptive_reports import (
    export_adaptive_csv,
    export_adaptive_html,
    export_adaptive_json,
    export_adaptive_markdown,
)

router = APIRouter(tags=["adaptive"])


@router.get("/adaptive/status")
async def adaptive_status(request: Request):
    _load_research_if_available(request)
    return _manager(request).status()


@router.get("/adaptive/selection")
async def adaptive_selection(
    request: Request,
    closes: str = Query("100,101,102,103"),
    asset: str = "btc_mxn",
    timeframe: str = "1m",
    top_n: int = 3,
):
    _load_research_if_available(request)
    values = tuple(float(item.strip()) for item in closes.split(",") if item.strip())
    return (
        _manager(request)
        .selection(closes=values, asset=asset, timeframe=timeframe, top_n=top_n)
        .to_public_dict()
    )


@router.get("/adaptive/portfolio")
async def adaptive_portfolio(
    request: Request, method: str = "score", max_weight: float = 0.5
):
    _load_research_if_available(request)
    return (
        _manager(request)
        .portfolio(method=method, max_weight=max_weight)
        .to_public_dict()
    )  # type: ignore[arg-type]


@router.get("/adaptive/report")
async def adaptive_report(request: Request, format: str = "json"):
    _load_research_if_available(request)
    data = _manager(request).report()
    if format == "csv":
        return {"format": "csv", "content": export_adaptive_csv(data)}
    if format == "markdown":
        return {"format": "markdown", "content": export_adaptive_markdown(data)}
    if format == "html":
        return {"format": "html", "content": export_adaptive_html(data)}
    return {"format": "json", "content": export_adaptive_json(data)}


def _manager(request: Request) -> AdaptiveManager:
    manager = getattr(request.app.state, "adaptive_manager", None)
    if manager is None:
        manager = AdaptiveManager()
        request.app.state.adaptive_manager = manager
    return manager


def _load_research_if_available(request: Request) -> None:
    research = getattr(request.app.state, "research_manager", None)
    current = getattr(research, "current_run", None)
    manager = _manager(request)
    if current is not None and not manager.registry.list():
        manager.load_research(current)
