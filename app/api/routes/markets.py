import asyncio
from datetime import datetime, timezone
import time

from fastapi import APIRouter, Query, Request, Response

from app.api.dependencies import require_auth
from app.services.bitso import BitsoError
from app.services.markets import build_market_catalog

router = APIRouter(tags=["markets"])
FALLBACK_TAKER_FEE_RATE = 0.0078
CATALOG_CACHE_SECONDS = 60
FALLBACK_BOOKS = {"btc_mxn", "eth_mxn", "sol_mxn", "xrp_mxn"}


async def _discover_books(client, enabled_books: set[str]) -> tuple[list[str], str]:
    try:
        result = await client.available_books()
        payload = result.get("payload", result)
        if isinstance(payload, dict):
            rows = payload.get("books") or payload.get("available_books") or []
        else:
            rows = payload

        available = {
            str(item.get("book", "")).lower()
            for item in rows
            if isinstance(item, dict)
            and str(item.get("book", "")).lower().endswith("_mxn")
        }
        discovered = sorted(enabled_books & available)
        if discovered:
            return discovered, "bitso_available_books"
    except (BitsoError, KeyError, TypeError, ValueError, AttributeError):
        pass

    return sorted(enabled_books & FALLBACK_BOOKS), "fallback_principal"


async def _safe_ticker(client, book: str) -> tuple[str, dict | None]:
    try:
        result = await client.ticker(book)
        ticker = result.get("payload", result)
        if float(ticker["last"]) <= 0:
            return book, None
        return book, ticker
    except (BitsoError, KeyError, TypeError, ValueError, AttributeError):
        return book, None


async def _fee_rates(client, books: set[str]) -> tuple[dict[str, float], str]:
    rates: dict[str, float] = {}
    source = "bitso_account"
    try:
        result = await client.fees()
        payload = result.get("payload", result)
        for item in payload.get("fees", []):
            book = str(item.get("book", "")).lower()
            raw_rate = item.get("taker_fee_decimal") or item.get("fee_decimal")
            if book and raw_rate is not None:
                parsed = float(raw_rate)
                if 0 <= parsed < 1:
                    rates[book] = parsed
    except (BitsoError, KeyError, TypeError, ValueError, AttributeError):
        source = "public_fallback"

    for book in books:
        rates.setdefault(book, FALLBACK_TAKER_FEE_RATE)
    return rates, source


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
    client = request.app.state.bitso
    books, discovery_source = await _discover_books(client, settings.allowed_books_set)
    ticker_pairs = await asyncio.gather(*(_safe_ticker(client, book) for book in books))
    tickers = {book: ticker for book, ticker in ticker_pairs if ticker is not None}
    valid_books = sorted(tickers)
    rates, fee_source = await _fee_rates(client, set(valid_books))
    items = build_market_catalog(valid_books, tickers, rates)

    result = {
        "items": items,
        "count": len(items),
        "discovery_source": discovery_source,
        "fee_source": fee_source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "refresh_seconds": CATALOG_CACHE_SECONDS,
        "live_trading_books": sorted(settings.live_books_set),
    }
    request.app.state.market_catalog_cache = result
    request.app.state.market_catalog_until = now + CATALOG_CACHE_SECONDS
    return result
