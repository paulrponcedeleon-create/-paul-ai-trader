from __future__ import annotations

import asyncio
from contextlib import suppress
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, FastAPI, Request

from app.brokers.exploration_persistent_paper import ExplorationPersistentPaperBroker
from app.paper_trading.exploration import ExplorationConfig
from app.runtime import RuntimeConfig
from app.runtime_exploration import ExplorationRuntimeEngine
from app.services.signal_levels import classify_signal_level

router = APIRouter(tags=["runtime"])

VERIFIED_RUNTIME_BOOKS = (
    "btc_mxn",
    "eth_mxn",
    "sol_mxn",
    "xrp_mxn",
    "usdt_mxn",
)


def _with_signal_level(decision: dict[str, Any] | None) -> dict[str, Any] | None:
    if not decision:
        return decision
    result = dict(decision)
    level = classify_signal_level(
        score=result.get("score", result.get("confidence", 0)),
        confidence=result.get("confidence", result.get("confidence_pct", 0)),
        action=str(result.get("action", "hold")),
    )
    result.update(level.to_public_dict())
    return result


@router.post("/runtime/start")
async def runtime_start(request: Request):
    runtime = _runtime(request)
    status = runtime.status() if runtime.running else await runtime.start()
    _ensure_background_loop(request, runtime)
    payload = status.to_public_dict()
    payload["last_decision"] = _with_signal_level(payload.get("last_decision"))
    return payload


@router.post("/runtime/stop")
async def runtime_stop(request: Request):
    runtime = _runtime(request)
    await _cancel_background_loop(request)
    status = await runtime.stop() if runtime.running else runtime.status()
    payload = status.to_public_dict()
    payload["last_decision"] = _with_signal_level(payload.get("last_decision"))
    return payload


@router.get("/runtime/status")
async def runtime_status(request: Request):
    runtime = _runtime(request)
    payload = runtime.status().to_public_dict()
    payload["last_decision"] = _with_signal_level(payload.get("last_decision"))
    for brain in payload.get("asset_brains", {}).values():
        classified = classify_signal_level(
            score=brain.get("last_score", 0),
            confidence=brain.get("last_confidence", 0),
            action=brain.get("last_action", "hold"),
        )
        brain.update(classified.to_public_dict())
    payload.update(
        {
            "automatic": bool(
                getattr(request.app.state.settings, "runtime_auto_start", True)
            ),
            "mode_label": (
                "Simulación automática"
                if not request.app.state.settings.live_trading
                else "Dinero real"
            ),
            "provider_label": (
                "Bitso, solo lectura"
                if runtime.config.market_data_provider == "bitso"
                else runtime.config.market_data_provider
            ),
            "broker_label": (
                "Dinero simulado"
                if runtime.config.broker_name == "paper"
                else runtime.config.broker_name
            ),
            "risk_label": (
                "Protección automática: pérdida 3%, objetivo 6% y seguimiento 2%"
            ),
            "history_label": (
                f"{payload.get('history_points', 0)} datos cargados para análisis"
            ),
            "signal_scale": [
                {"color": "blue", "label": "Oportunidad excepcional"},
                {"color": "green", "label": "Favorable"},
                {"color": "yellow", "label": "Mantener y observar"},
                {"color": "orange", "label": "Desfavorable"},
                {"color": "red", "label": "Riesgo alto / salida"},
            ],
        }
    )
    return payload


@router.get("/runtime/components")
async def runtime_components(request: Request):
    return _runtime(request).components()


@router.get("/runtime/config")
async def runtime_config(request: Request):
    runtime = _runtime(request)
    payload = runtime.config.to_public_dict()
    payload["exploration"] = runtime.status().to_public_dict().get("exploration")
    return payload


async def shutdown_runtime(application: FastAPI) -> None:
    """Cancel Runtime background work and disconnect an existing Runtime engine."""
    await _cancel_background_task(application)
    runtime = getattr(application.state, "runtime_engine", None)
    if runtime is not None and runtime.running:
        await runtime.stop()


async def _background_loop(runtime: ExplorationRuntimeEngine) -> None:
    while True:
        await runtime.run_once()
        await asyncio.sleep(max(runtime.config.loop_interval_seconds, 5.0))


async def _cancel_background_loop(request: Request) -> None:
    await _cancel_background_task(request.app)


async def _cancel_background_task(application: FastAPI) -> None:
    task = getattr(application.state, "runtime_background_task", None)
    application.state.runtime_background_task = None
    if task is None:
        return
    if not task.done():
        task.cancel()
    with suppress(asyncio.CancelledError, Exception):
        await task


def _ensure_background_loop(
    request: Request, runtime: ExplorationRuntimeEngine
) -> None:
    settings = request.app.state.settings
    if not bool(getattr(settings, "runtime_auto_start", True)):
        return
    task = getattr(request.app.state, "runtime_background_task", None)
    if task is None or task.done():
        request.app.state.runtime_background_task = asyncio.create_task(
            _background_loop(runtime), name="paul-ai-paper-runtime"
        )


def _resolved_runtime_books(settings) -> tuple[str, ...]:
    configured = tuple(
        book.strip().lower()
        for book in getattr(
            settings,
            "runtime_books",
            ",".join(VERIFIED_RUNTIME_BOOKS),
        ).split(",")
        if book.strip()
    )
    verified = tuple(book for book in configured if book in VERIFIED_RUNTIME_BOOKS)
    return verified or VERIFIED_RUNTIME_BOOKS


def _runtime(request: Request) -> ExplorationRuntimeEngine:
    runtime = getattr(request.app.state, "runtime_engine", None)
    if runtime is None:
        settings = request.app.state.settings
        config = RuntimeConfig(
            loop_interval_seconds=float(
                getattr(settings, "runtime_loop_interval_seconds", 60.0)
            ),
            books=_resolved_runtime_books(settings),
            timeframe=getattr(settings, "runtime_timeframe", "1m"),
            strategy_name=getattr(settings, "runtime_strategy", "momentum"),
            trade_amount_mxn=Decimal(
                str(getattr(settings, "runtime_trade_amount_mxn", 100))
            ),
            market_data_provider=getattr(
                settings, "runtime_market_data_provider", "bitso"
            ),
            broker_name=getattr(settings, "runtime_broker", "paper"),
            max_history=int(getattr(settings, "runtime_history_points", 200)),
        )
        exploration_config = ExplorationConfig(
            enabled=bool(getattr(settings, "paper_exploration_enabled", True)),
            hold_cycles_before_entry=int(
                getattr(settings, "paper_exploration_hold_cycles", 20)
            ),
            max_holding_cycles=int(
                getattr(settings, "paper_exploration_max_holding_cycles", 20)
            ),
            cooldown_cycles=int(
                getattr(settings, "paper_exploration_cooldown_cycles", 40)
            ),
            amount_mxn=Decimal(
                str(getattr(settings, "paper_exploration_amount_mxn", 10))
            ),
        )
        broker = None
        if config.broker_name == "paper":
            broker = ExplorationPersistentPaperBroker(
                session_factory=request.app.state.db_session_factory,
                settings=settings,
            )
        runtime = ExplorationRuntimeEngine(
            config=config,
            exploration_config=exploration_config,
            live_trading=bool(settings.live_trading),
            broker=broker,
            settings=settings,
        )
        request.app.state.runtime_engine = runtime
    return runtime
