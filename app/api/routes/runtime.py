from __future__ import annotations

import asyncio
from contextlib import suppress
from decimal import Decimal

from fastapi import APIRouter, FastAPI, Request

from app.runtime import RuntimeConfig, RuntimeEngine

router = APIRouter(tags=["runtime"])

VERIFIED_RUNTIME_BOOKS = (
    "btc_mxn",
    "eth_mxn",
    "sol_mxn",
    "xrp_mxn",
    "usdt_mxn",
)


@router.post("/runtime/start")
async def runtime_start(request: Request):
    runtime = _runtime(request)
    status = runtime.status() if runtime.running else await runtime.start()
    _ensure_background_loop(request, runtime)
    return status.to_public_dict()


@router.post("/runtime/stop")
async def runtime_stop(request: Request):
    runtime = _runtime(request)
    await _cancel_background_loop(request)
    status = await runtime.stop() if runtime.running else runtime.status()
    return status.to_public_dict()


@router.get("/runtime/status")
async def runtime_status(request: Request):
    runtime = _runtime(request)
    payload = runtime.status().to_public_dict()
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
        }
    )
    return payload


@router.get("/runtime/components")
async def runtime_components(request: Request):
    return _runtime(request).components()


@router.get("/runtime/config")
async def runtime_config(request: Request):
    return _runtime(request).config.to_public_dict()


async def shutdown_runtime(application: FastAPI) -> None:
    """Cancel Runtime background work and disconnect an existing Runtime engine."""
    await _cancel_background_task(application)
    runtime = getattr(application.state, "runtime_engine", None)
    if runtime is not None and runtime.running:
        await runtime.stop()


async def _background_loop(runtime: RuntimeEngine) -> None:
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


def _ensure_background_loop(request: Request, runtime: RuntimeEngine) -> None:
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


def _runtime(request: Request) -> RuntimeEngine:
    runtime = getattr(request.app.state, "runtime_engine", None)
    if runtime is None:
        settings = request.app.state.settings
        runtime = RuntimeEngine(
            config=RuntimeConfig(
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
            ),
            settings=settings,
        )
        request.app.state.runtime_engine = runtime
    return runtime
