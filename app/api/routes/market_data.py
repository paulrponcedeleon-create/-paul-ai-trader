from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.market_data import (
    MarketDataCache,
    MarketDataProvider,
    ProviderFactory,
    WebSocketController,
)
from app.reporting.market_data_reports import market_data_quality_report

router = APIRouter(tags=["market-data"])


@router.get("/market/live/status")
async def market_live_status(request: Request):
    provider = _provider(request)
    status = provider.status().to_public_dict()
    return market_data_quality_report(
        status=status,
        events=[event.to_public_dict() for event in _cache(request).events],
    )


@router.get("/market/live/provider")
async def market_live_provider(request: Request):
    provider = _provider(request)
    return provider.status().to_public_dict()


@router.get("/market/live/ticker")
async def market_live_ticker(request: Request, book: str = Query("btc_mxn")):
    ticker = await _provider(request).get_ticker(book.lower())
    return ticker.to_public_dict()


@router.get("/market/live/orderbook")
async def market_live_orderbook(request: Request, book: str = Query("btc_mxn")):
    orderbook = await _provider(request).get_orderbook(book.lower())
    return orderbook.to_public_dict()


@router.get("/market/live/candles")
async def market_live_candles(
    request: Request,
    book: str = Query("btc_mxn"),
    timeframe: str = Query("1m"),
    limit: int = Query(100, ge=1, le=500),
):
    candles = await _provider(request).get_candles(book.lower(), timeframe, limit)
    return {"items": [candle.to_public_dict() for candle in candles]}


@router.get("/market/live/trades")
async def market_live_trades(
    request: Request,
    book: str = Query("btc_mxn"),
    limit: int = Query(100, ge=1, le=500),
):
    trades = await _provider(request).get_recent_trades(book.lower(), limit)
    return {"items": [trade.to_public_dict() for trade in trades]}


def _cache(request: Request) -> MarketDataCache:
    cache = getattr(request.app.state, "market_data_cache", None)
    if cache is None:
        cache = MarketDataCache()
        request.app.state.market_data_cache = cache
    return cache


def _provider(request: Request) -> MarketDataProvider:
    provider = getattr(request.app.state, "market_data_provider", None)
    if provider is None:
        provider = ProviderFactory(
            settings=request.app.state.settings,
            bitso_client=getattr(request.app.state, "bitso", None),
            cache=_cache(request),
        ).create("mock")
        request.app.state.market_data_provider = provider
        request.app.state.market_data_ws = WebSocketController(provider)
    return provider
