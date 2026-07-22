import asyncio
from datetime import date, datetime, timezone
from pathlib import Path
import secrets
import time

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api.dependencies import authenticated, require_auth
from app.api.routes.auth import router as auth_router
from app.api.routes.readiness import router as readiness_router
from app.api.routes.pro_strategy import router as pro_strategy_router
from app.api.routes.optimization import router as optimization_router
from app.api.routes.paper import router as paper_router
from app.api.routes.ai import router as ai_router
from app.api.routes.broker import router as broker_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.market_data import router as market_data_router
from app.api.routes.live import router as live_router
from app.api.routes.system import router as system_router
from app.api.routes.runtime import router as runtime_router
from app.api.routes.burnin import router as burnin_router
from app.api.routes.experiments import router as experiments_router
from app.api.routes.research import router as research_router
from app.api.routes.adaptive import router as adaptive_router
from app.api.routes.validation import router as validation_router
from app.config import Settings, settings
from app.db.base import Base
from app.db.session import build_engine, build_session_factory
from app.models import SimulatedOrderRequest
from app.repositories.simulated_orders import SqlSimulatedOrderRepository
from app.services.bitso import BitsoClient, BitsoError
from app.services.performance import resolve_period_range, summarize_closed_orders
from app.services.portfolio import calculate_position, summarize_positions
from app.services.risk import validate_order
from app.services.store import add_simulation, list_simulations
from app.services.signals import momentum_signal

BASE_DIR = Path(__file__).resolve().parent
FALLBACK_TAKER_FEE_RATE = 0.0078
FEE_CACHE_SECONDS = 900
PERFORMANCE_TIMEZONE = "America/Ciudad_Juarez"


def create_app(
    app_settings: Settings | None = None,
    bitso_client: BitsoClient | None = None,
) -> FastAPI:
    current_settings = app_settings or settings
    current_bitso = bitso_client or BitsoClient(current_settings)
    engine = build_engine(current_settings)
    session_factory = build_session_factory(engine)

    # Tests use isolated temporary databases. Real environments must apply
    # schema changes through Alembic so alembic_version remains authoritative.
    if current_settings.app_env == "test":
        Base.metadata.create_all(bind=engine)

    application = FastAPI(title=current_settings.app_name, version="1.0.0")
    application.add_middleware(
        SessionMiddleware,
        secret_key=current_settings.session_secret,
        session_cookie=current_settings.session_cookie_name,
        max_age=current_settings.session_max_age_seconds,
        same_site=current_settings.session_cookie_samesite,
        https_only=current_settings.resolved_session_cookie_secure,
    )
    application.mount(
        "/static", StaticFiles(directory=BASE_DIR / "static"), name="static"
    )
    templates = Jinja2Templates(directory=BASE_DIR / "templates")

    application.state.settings = current_settings
    application.state.bitso = current_bitso
    application.state.db_engine = engine
    application.state.db_session_factory = session_factory
    application.include_router(auth_router)
    application.include_router(readiness_router)
    application.include_router(pro_strategy_router)
    application.include_router(optimization_router)
    application.include_router(paper_router)
    application.include_router(ai_router)
    application.include_router(broker_router)
    application.include_router(analytics_router)
    application.include_router(market_data_router)
    application.include_router(live_router)
    application.include_router(system_router)
    application.include_router(runtime_router)
    application.include_router(burnin_router)
    application.include_router(experiments_router)
    application.include_router(research_router)
    application.include_router(adaptive_router)
    application.include_router(validation_router)

    fee_cache: dict[str, float] = {}
    fee_cache_source = "public_fallback"
    fee_cache_until = 0.0

    async def get_market_ticker(book: str) -> dict:
        try:
            result = await current_bitso.ticker(book)
            ticker = result.get("payload", result)
            if float(ticker["last"]) <= 0:
                raise ValueError("Precio de mercado inválido.")
            return ticker
        except (BitsoError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    async def get_taker_fee_rates(books: set[str]) -> tuple[dict[str, float], str]:
        nonlocal fee_cache_source, fee_cache_until
        if not books:
            return {}, fee_cache_source

        now = time.monotonic()
        if now < fee_cache_until and all(book in fee_cache for book in books):
            return {book: fee_cache[book] for book in books}, fee_cache_source

        rates: dict[str, float] = {}
        source = "bitso_account"
        try:
            result = await current_bitso.fees()
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

        fee_cache.update(rates)
        fee_cache_source = source
        fee_cache_until = now + FEE_CACHE_SECONDS
        return {book: fee_cache[book] for book in books}, fee_cache_source

    def template_context(request: Request) -> dict:
        return {
            "app_name": current_settings.app_name,
            "authenticated": authenticated(request),
            "live_trading": current_settings.live_trading,
            "max_order": current_settings.max_order_mxn,
            "allowed_books": sorted(current_settings.allowed_books_set),
        }

    @application.on_event("shutdown")
    def dispose_database_engine() -> None:
        engine.dispose()

    @application.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "mode": "live" if current_settings.live_trading else "simulation",
        }

    @application.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=template_context(request),
        )

    @application.get("/performance", response_class=HTMLResponse)
    async def performance_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="performance.html",
            context=template_context(request),
        )

    @application.get("/api/config")
    async def config(request: Request):
        require_auth(request)
        return {
            "mode": "LIVE" if current_settings.live_trading else "SIMULATION",
            "allowed_books": sorted(current_settings.allowed_books_set),
            "max_order_mxn": current_settings.max_order_mxn,
            "max_daily_loss_mxn": current_settings.max_daily_loss_mxn,
            "max_open_orders": current_settings.max_open_orders,
            "bitso_connected": bool(
                current_settings.bitso_api_key and current_settings.bitso_api_secret
            ),
        }

    @application.get("/api/market/{book}")
    async def market(book: str, request: Request, response: Response):
        require_auth(request)
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        book = book.lower()
        if book not in current_settings.allowed_books_set:
            raise HTTPException(status_code=403, detail="Mercado no autorizado.")

        ticker = await get_market_ticker(book)
        try:
            signal = momentum_signal(
                last=float(ticker["last"]),
                high=float(ticker["high"]),
                low=float(ticker["low"]),
                volume=float(ticker.get("volume", 0)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return {
            "book": book,
            "ticker": ticker,
            "signal": signal.__dict__,
            "warning": "Señal educativa; no garantiza ganancias.",
        }

    @application.get("/api/balance")
    async def balance(request: Request):
        require_auth(request)
        try:
            return await current_bitso.balance()
        except BitsoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/simulations")
    async def simulations(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ):
        require_auth(request)
        with session_factory() as db_session:
            repository = SqlSimulatedOrderRepository(db_session)
            return list_simulations(repository, limit=limit, offset=offset)

    @application.get("/api/performance")
    async def performance(
        request: Request,
        response: Response,
        period: str = Query(default="30d"),
        books: str | None = Query(default=None),
        start: date | None = Query(default=None),
        end: date | None = Query(default=None),
    ):
        require_auth(request)
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"

        selected_books = {
            value.strip().lower() for value in (books or "").split(",") if value.strip()
        }
        invalid_books = selected_books - current_settings.allowed_books_set
        if invalid_books:
            raise HTTPException(
                status_code=403, detail="Una o más criptomonedas no están autorizadas."
            )

        try:
            start_at, end_at, period_label = resolve_period_range(
                period,
                start_date=start,
                end_date=end,
                timezone_name=PERFORMANCE_TIMEZONE,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        with session_factory() as db_session:
            repository = SqlSimulatedOrderRepository(db_session)
            closed_orders = repository.list_closed(
                start_at=start_at,
                end_at=end_at,
                books=selected_books or None,
            )

        result = summarize_closed_orders(
            closed_orders,
            timezone_name=PERFORMANCE_TIMEZONE,
        )
        return {
            **result,
            "period": period,
            "period_label": period_label,
            "selected_books": sorted(selected_books),
            "start_at": start_at.isoformat() if start_at else None,
            "end_at": end_at.isoformat() if end_at else None,
            "timezone": PERFORMANCE_TIMEZONE,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @application.get("/api/positions")
    async def positions(request: Request, response: Response):
        require_auth(request)
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"

        with session_factory() as db_session:
            repository = SqlSimulatedOrderRepository(db_session)
            open_orders = repository.list_open()

        books = sorted({str(item["book"]) for item in open_orders})
        if books:
            ticker_results, fee_result = await asyncio.gather(
                asyncio.gather(*(get_market_ticker(book) for book in books)),
                get_taker_fee_rates(set(books)),
            )
            fee_rates, fee_source = fee_result
            prices = {
                book: float(ticker["last"])
                for book, ticker in zip(books, ticker_results, strict=True)
            }
        else:
            prices = {}
            fee_rates = {}
            fee_source = fee_cache_source

        items = [
            calculate_position(
                item,
                prices[str(item["book"])],
                exit_fee_rate=fee_rates.get(str(item["book"]), FALLBACK_TAKER_FEE_RATE),
            )
            for item in open_orders
        ]
        return {
            "items": items,
            "summary": summarize_positions(items),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "refresh_seconds": 5,
            "fees_included": True,
            "fee_source": fee_source,
        }

    @application.post("/api/simulations/{simulation_id}/close")
    async def close_simulation(simulation_id: str, request: Request):
        require_auth(request)
        with session_factory() as db_session:
            repository = SqlSimulatedOrderRepository(db_session)
            open_order = repository.get_open(simulation_id)

        if open_order is None:
            raise HTTPException(
                status_code=404,
                detail="La posición no existe o ya fue cerrada.",
            )

        book = str(open_order["book"])
        ticker, fee_result = await asyncio.gather(
            get_market_ticker(book),
            get_taker_fee_rates({book}),
        )
        fee_rates, _ = fee_result
        exit_fee_rate = fee_rates[book]
        close_price = float(ticker["last"])
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
                raise HTTPException(
                    status_code=409,
                    detail="La posición ya fue cerrada.",
                )
            db_session.commit()

        return {
            **closed,
            "asset_quantity": calculated["asset_quantity"],
            "current_value_mxn": calculated["current_value_mxn"],
            "return_pct": calculated["return_pct"],
            "total_estimated_fees_mxn": calculated["total_estimated_fees_mxn"],
        }

    @application.post("/api/orders")
    async def order(body: SimulatedOrderRequest, request: Request):
        require_auth(request)
        decision = validate_order(
            body.book,
            body.side,
            body.amount_mxn,
            body.daily_pnl_mxn,
            body.open_orders,
            current_settings,
        )
        if not decision.allowed:
            raise HTTPException(status_code=403, detail=decision.reason)

        if not current_settings.live_trading:
            book = body.book.lower()
            ticker, fee_result = await asyncio.gather(
                get_market_ticker(book),
                get_taker_fee_rates({book}),
            )
            fee_rates, fee_source = fee_result
            entry_fee_rate = fee_rates[book]
            entry_price = float(ticker["last"])
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
            with session_factory() as db_session:
                repository = SqlSimulatedOrderRepository(db_session)
                saved_item = add_simulation(item, repository)
                db_session.commit()
                return {
                    **saved_item,
                    "status": "simulated",
                    "position_status": saved_item["status"],
                    "fee_source": fee_source,
                }

        try:
            result = await current_bitso.place_market_order(
                body.book.lower(), body.side, body.amount_mxn
            )
        except BitsoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "submitted", "risk_check": decision.reason, "bitso": result}

    return application


app = create_app()
