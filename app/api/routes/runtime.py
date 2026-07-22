from __future__ import annotations

from decimal import Decimal
from fastapi import APIRouter, Request

from app.runtime import RuntimeConfig, RuntimeEngine

router = APIRouter(tags=["runtime"])


@router.post("/runtime/start")
async def runtime_start(request: Request):
    return (await _runtime(request).start()).to_public_dict()


@router.post("/runtime/stop")
async def runtime_stop(request: Request):
    return (await _runtime(request).stop()).to_public_dict()


@router.get("/runtime/status")
async def runtime_status(request: Request):
    return _runtime(request).status().to_public_dict()


@router.get("/runtime/components")
async def runtime_components(request: Request):
    return _runtime(request).components()


@router.get("/runtime/config")
async def runtime_config(request: Request):
    return _runtime(request).config.to_public_dict()


def _runtime(request: Request) -> RuntimeEngine:
    runtime = getattr(request.app.state, "runtime_engine", None)
    if runtime is None:
        settings = request.app.state.settings
        books = tuple(getattr(settings, "runtime_books", "btc_mxn").split(","))
        runtime = RuntimeEngine(
            config=RuntimeConfig(
                loop_interval_seconds=float(
                    getattr(settings, "runtime_loop_interval_seconds", 5.0)
                ),
                books=tuple(book.strip().lower() for book in books if book.strip()),
                timeframe=getattr(settings, "runtime_timeframe", "1m"),
                strategy_name=getattr(settings, "runtime_strategy", "momentum"),
                trade_amount_mxn=Decimal(
                    str(getattr(settings, "runtime_trade_amount_mxn", 100))
                ),
                market_data_provider=getattr(
                    settings, "runtime_market_data_provider", "mock"
                ),
                broker_name=getattr(settings, "runtime_broker", "paper"),
            ),
            settings=settings,
        )
        request.app.state.runtime_engine = runtime
    return runtime
