from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.market_data import (
    MarketDataCache,
    MarketDataProvider,
    ProviderFactory,
    WebSocketController,
)
from app.reporting.market_data_reports import market_data_quality_report
from app.services.bitso import BitsoError

router = APIRouter(tags=["market-data"])

RFQ_BOOKS = {
    "atom_mxn": "ATOM",
    "paxg_mxn": "PAXG",
    "usdc_mxn": "USDC",
}


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


@router.get("/market/rfq/{book}")
async def market_rfq_ticker(book: str, request: Request):
    """Return a Bitso RFQ valuation for assets without a public MXN order book.

    The quote is read-only and is used only in simulation. It never places an
    order and does not enable LIVE_TRADING.
    """
    normalized = book.lower()
    source = RFQ_BOOKS.get(normalized)
    if source is None:
        raise HTTPException(status_code=404, detail="Activo RFQ no configurado.")

    try:
        result = await request.app.state.bitso.rfq_quote(
            source=source,
            target="MXN",
            source_amount="1",
        )
    except BitsoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    payload = result.get("payload", result)
    if isinstance(payload, dict) and isinstance(payload.get("quote"), dict):
        payload = payload["quote"]

    candidates = (
        payload.get("target_amount") if isinstance(payload, dict) else None,
        payload.get("amount") if isinstance(payload, dict) else None,
        payload.get("price") if isinstance(payload, dict) else None,
        payload.get("rate") if isinstance(payload, dict) else None,
    )
    price = next((value for value in candidates if value not in (None, "")), None)
    try:
        last = float(price)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Bitso RFQ respondió sin un precio MXN reconocible.",
        ) from exc
    if last <= 0:
        raise HTTPException(status_code=502, detail="Bitso RFQ devolvió un precio inválido.")

    return {
        "book": normalized,
        "ticker": {
            "book": normalized,
            "last": last,
            "high": last,
            "low": last,
            "volume": 0,
            "source": "bitso_rfq",
            "route_label": f"Bitso RFQ · {source} → MXN",
            "fee_included_in_quote": True,
        },
        "signal": {
            "action": "hold",
            "score": 50,
            "confidence": 0,
            "reason": "Cotización RFQ disponible; faltan velas públicas para calcular señal.",
        },
        "warning": "Cotización educativa de Bitso RFQ; no ejecuta órdenes.",
    }


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
        ).create("bitso")
        request.app.state.market_data_provider = provider
        request.app.state.market_data_ws = WebSocketController(provider)
    return provider
