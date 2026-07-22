from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.burnin import BurnInConfig, BurnInManager
from app.reporting.burnin_reports import (
    export_burnin_csv,
    export_burnin_html,
    export_burnin_json,
    export_burnin_markdown,
)

router = APIRouter(tags=["burnin"])


@router.post("/burnin/start")
async def burnin_start(
    request: Request,
    duration: str | None = Query(None, pattern="^(1h|6h|12h|24h|72h|custom)$"),
    custom_duration_seconds: float | None = None,
    max_cycles: int | None = Query(None, ge=1),
):
    settings = request.app.state.settings
    manager = _manager(
        request,
        BurnInConfig(
            duration=duration or getattr(settings, "burnin_default_duration", "1h"),  # type: ignore[arg-type]
            custom_duration_seconds=custom_duration_seconds,
            max_cycles=max_cycles,
            memory_growth_alert_bytes=int(
                getattr(settings, "burnin_memory_growth_alert_bytes", 26214400)
            ),
            max_events=int(getattr(settings, "burnin_max_events", 1000)),
        ),
    )
    return manager.start_background().to_public_dict()


@router.post("/burnin/stop")
async def burnin_stop(request: Request):
    return (await _manager(request).stop()).to_public_dict()


@router.get("/burnin/status")
async def burnin_status(request: Request):
    return _manager(request).status()


@router.get("/burnin/report")
async def burnin_report(request: Request, format: str = "json"):
    report = _manager(request).report()
    if format == "csv":
        return {"format": "csv", "content": export_burnin_csv(report)}
    if format == "markdown":
        return {"format": "markdown", "content": export_burnin_markdown(report)}
    if format == "html":
        return {"format": "html", "content": export_burnin_html(report)}
    return {"format": "json", "content": export_burnin_json(report)}


def _manager(request: Request, config: BurnInConfig | None = None) -> BurnInManager:
    manager = getattr(request.app.state, "burnin_manager", None)
    if manager is None or config is not None:
        runtime = getattr(request.app.state, "runtime_engine", None)
        if runtime is None:
            from app.api.routes.runtime import _runtime

            runtime = _runtime(request)
        manager = BurnInManager(runtime, config)
        request.app.state.burnin_manager = manager
    return manager
