from datetime import datetime, timezone
import secrets
import time

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.api.dependencies import require_auth
from app.models import SimulatedOrderRequest
from app.repositories.simulated_orders import SqlSimulatedOrderRepository
from app.services.bitso import BitsoError
from app.services.portfolio import calculate_position, summarize_positions
from app.services.risk import validate_order
from app.services.store import add_simulation
from app.services.strategy import momentum_signal
from app.services.unified_markets import UnifiedMarketError, UnifiedMarketService

router = APIRouter(tags=["markets"])
CATALOG_CACHE_SECONDS = 30


def _market_service(request: Request) -> UnifiedMarketService:
    service = getattr(request.app.state, "unified_markets", None)
    if service is None:
        service = UnifiedMarketService(request.app.state.bitso)
        request.app.state.unified_markets = service
    return service


@router.get("/markets")
async def markets(
    request: Request,
    response: Response,
    force: bool = Query(default=False),
):
    require_auth(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"

    now = time.monotonic()
    cached = getattr(request.app.state, "market_catalog_cache", None)
    cache_until = getattr(request.app.state, "market_catalog_until", 0.0)
    if not force and cached and now < cache_until:
        return cached

    settings = request.app.state.settings
    service = _market_service(request)
    items = await service.catalog(settings.allowed_books_set)
    result = {
        "items": items,
        "count": len(items),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "refresh_seconds": CATALOG_CACHE_SECONDS,
        "live_trading_books": sorted(settings.live_books_set),
    }
    request.app.state.market_catalog_cache = result
    request.app.state.market_catalog_until = now + CATALOG_CACHE_SECONDS
    return result


@router.get("/market/{book}")
async def market(book: str, request: Request, response: Response):
    require_auth(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    settings = request.app.state.settings
    book = book.lower()
    if book not in settings.allowed_books_set:
        raise HTTPException(status_code=403, detail="Mercado no autorizado.")

    try:
        quote = await _market_service(request).quote(book, force=True, side="buy")
        signal = (
            momentum_signal(
                last=float(quote["last"]),
                high=float(quote["high"]),
                low=float(quote["low"]),
                volume=float(quote.get("volume", 0)),
            )
            if quote["asset_type"] != "cash" and quote["source"] != "bitso_rfq"
            else None
        )
    except (UnifiedMarketError, BitsoError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if quote["asset_type"] == "cash":
        reason = "Efectivo disponible; no tiene movimiento de mercado."
        confidence = 100
    elif quote["source"] == "bitso_rfq":
        reason = "Conversión disponible en Bitso App; no hay rango Alpha de 24 h comparable."
        confidence = 50
    else:
        reason = signal.reason
        confidence = signal.confidence

    signal_payload = (
        signal.__dict__
        if signal is not None
        else {
            "action": "hold",
            "confidence": confidence,
            "reason": reason,
            "reference_price": float(quote["last"]),
        }
    )
    return {
        "book": book,
        "ticker": quote,
        "signal": signal_payload,
        "warning": "Señal educativa; no garantiza ganancias.",
    }


@router.get("/positions")
async def positions(request: Request, response: Response):
    require_auth(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    session_factory = request.app.state.db_session_factory
    with session_factory() as db_session:
        repository = SqlSimulatedOrderRepository(db_session)
        open_orders = repository.list_open()

    service = _market_service(request)
    items = []
    fee_sources: set[str] = set()
    for item in open_orders:
        close_side = "sell" if item["side"] == "buy" else "buy"
        try:
            quote = await service.quote(
                str(item["book"]),
                force=True,
                side=close_side,
            )
        except (UnifiedMarketError, BitsoError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        fee_sources.add(str(quote["fee_source"]))
        calculated = calculate_position(
            item,
            float(quote["last"]),
            exit_fee_rate=float(quote["effective_fee_rate"]),
        )
        calculated.update(
            {
                "symbol": quote["symbol"],
                "name": quote["name"],
                "asset_type": quote["asset_type"],
                "route": quote["route"],
                "route_label": quote.get("route_label"),
                "quote_source": quote["source"],
                "fee_included_in_quote": quote.get("fee_included_in_quote", False),
                "delayed": quote["delayed"],
            }
        )
        items.append(calculated)

    return {
        "items": items,
        "summary": summarize_positions(items),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "refresh_seconds": 5,
        "fees_included": True,
        "fee_source": "mixed" if len(fee_sources) > 1 else next(iter(fee_sources), "none"),
    }


@router.post("/simulations/{simulation_id}/close")
async def close_simulation(simulation_id: str, request: Request):
    require_auth(request)
    session_factory = request.app.state.db_session_factory
    with session_factory() as db_session:
        repository = SqlSimulatedOrderRepository(db_session)
        open_order = repository.get_open(simulation_id)

    if open_order is None:
        raise HTTPException(status_code=404, detail="La posición no existe o ya fue cerrada.")

    close_side = "sell" if open_order["side"] == "buy" else "buy"
    try:
        quote = await _market_service(request).quote(
            str(open_order["book"]),
            force=True,
            side=close_side,
        )
    except (UnifiedMarketError, BitsoError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    exit_fee_rate = float(quote["effective_fee_rate"])
    close_price = float(quote["last"])
    calculated = calculate_position(
        open_order,
        close_price,
        exit_fee_rate=exit_fee_rate,
    )
    closed_at = datetime.now(timezone.utc)

    with session_factory() as db_session:
        repository = SqlSimulatedOrderRepository(db_session)
        closed = repository.close(
            simulation_id,
            closed_at=closed_at,
            close_price=close_price,
            exit_fee_rate=exit_fee_rate,
            exit_fee_mxn=float(calculated["estimated_exit_fee_mxn"]),
            realized_pnl_mxn=float(calculated["unrealized_pnl_mxn"]),
        )
        if closed is None:
            raise HTTPException(status_code=409, detail="La posición ya fue cerrada.")
        db_session.commit()

    return {
        **closed,
        "symbol": quote["symbol"],
        "name": quote["name"],
        "asset_type": quote["asset_type"],
        "asset_quantity": calculated["asset_quantity"],
        "current_value_mxn": calculated["current_value_mxn"],
        "return_pct": calculated["return_pct"],
        "total_estimated_fees_mxn": calculated["total_estimated_fees_mxn"],
    }


@router.post("/orders")
async def order(body: SimulatedOrderRequest, request: Request):
    require_auth(request)
    settings = request.app.state.settings
    decision = validate_order(
        body.book,
        body.side,
        body.amount_mxn,
        body.daily_pnl_mxn,
        body.open_orders,
        settings,
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)

    book = body.book.lower()
    try:
        quote = await _market_service(request).quote(
            book,
            force=True,
            side=body.side,
        )
    except (UnifiedMarketError, BitsoError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not quote["tradeable"]:
        raise HTTPException(status_code=403, detail="Este activo es informativo y no abre posiciones.")

    if settings.live_trading:
        if quote["asset_type"] != "crypto" or quote["route"] != [book]:
            raise HTTPException(
                status_code=403,
                detail="El modo real solo permite libros cripto autorizados directamente contra MXN.",
            )
        try:
            result = await request.app.state.bitso.place_market_order(
                book, body.side, body.amount_mxn
            )
        except BitsoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "submitted", "risk_check": decision.reason, "bitso": result}

    entry_fee_rate = float(quote["effective_fee_rate"])
    entry_price = float(quote["last"])
    item = {
        "id": secrets.token_hex(6),
        "created_at": datetime.now(timezone.utc),
        "status": "open",
        "book": book,
        "side": body.side,
        "amount_mxn": round(body.amount_mxn, 2),
        "reference_price": entry_price,
        "entry_fee_rate": entry_fee_rate,
        "entry_fee_mxn": round(body.amount_mxn * entry_fee_rate, 2),
        "risk_check": decision.reason,
    }
    session_factory = request.app.state.db_session_factory
    with session_factory() as db_session:
        repository = SqlSimulatedOrderRepository(db_session)
        saved_item = add_simulation(item, repository)
        db_session.commit()

    return {
        **saved_item,
        "status": "simulated",
        "position_status": saved_item["status"],
        "symbol": quote["symbol"],
        "name": quote["name"],
        "asset_type": quote["asset_type"],
        "route": quote["route"],
        "route_label": quote.get("route_label"),
        "fee_source": quote["fee_source"],
        "fee_included_in_quote": quote.get("fee_included_in_quote", False),
    }
