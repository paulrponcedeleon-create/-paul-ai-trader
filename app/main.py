from datetime import datetime, timezone
from pathlib import Path
import secrets

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api.dependencies import authenticated, require_auth
from app.api.routes.auth import router as auth_router
from app.config import Settings, settings
from app.db.base import Base
from app.db.session import build_engine, build_session_factory
from app.models import SimulatedOrderRequest
from app.repositories.simulated_orders import SqlSimulatedOrderRepository
from app.services.bitso import BitsoClient, BitsoError
from app.services.portfolio import calculate_position, summarize_positions
from app.services.risk import validate_order
from app.services.store import add_simulation, list_simulations
from app.services.strategy import momentum_signal

BASE_DIR = Path(__file__).resolve().parent


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
    application.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=BASE_DIR / "templates")

    application.state.settings = current_settings
    application.state.bitso = current_bitso
    application.state.db_engine = engine
    application.state.db_session_factory = session_factory
    application.include_router(auth_router)

    async def get_market_ticker(book: str) -> dict:
        try:
            result = await current_bitso.ticker(book)
            ticker = result.get("payload", result)
            if float(ticker["last"]) <= 0:
                raise ValueError("Precio de mercado inválido.")
            return ticker
        except (BitsoError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

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
            context={
                "app_name": current_settings.app_name,
                "authenticated": authenticated(request),
                "live_trading": current_settings.live_trading,
                "max_order": current_settings.max_order_mxn,
                "allowed_books": sorted(current_settings.allowed_books_set),
            },
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
    async def market(book: str, request: Request):
        require_auth(request)
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

    @application.get("/api/positions")
    async def positions(request: Request):
        require_auth(request)
        with session_factory() as db_session:
            repository = SqlSimulatedOrderRepository(db_session)
            open_orders = repository.list_open()

        prices: dict[str, float] = {}
        for book in sorted({str(item["book"]) for item in open_orders}):
            ticker = await get_market_ticker(book)
            prices[book] = float(ticker["last"])

        items = [
            calculate_position(item, prices[str(item["book"])])
            for item in open_orders
        ]
        return {
            "items": items,
            "summary": summarize_positions(items),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "fees_included": False,
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

        ticker = await get_market_ticker(str(open_order["book"]))
        close_price = float(ticker["last"])
        calculated = calculate_position(open_order, close_price)
        closed_at = datetime.now(timezone.utc)

        with session_factory() as db_session:
            repository = SqlSimulatedOrderRepository(db_session)
            closed = repository.close(
                simulation_id,
                closed_at=closed_at,
                close_price=close_price,
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
            ticker = await get_market_ticker(book)
            entry_price = float(ticker["last"])
            item = {
                "id": secrets.token_hex(6),
                "created_at": datetime.now(timezone.utc),
                "status": "open",
                "book": book,
                "side": body.side,
                "amount_mxn": round(body.amount_mxn, 2),
                "reference_price": entry_price,
                "risk_check": decision.reason,
            }
            with session_factory() as db_session:
                repository = SqlSimulatedOrderRepository(db_session)
                saved_item = add_simulation(item, repository)
                db_session.commit()
                return saved_item

        try:
            result = await current_bitso.place_market_order(
                body.book.lower(), body.side, body.amount_mxn
            )
        except BitsoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "submitted", "risk_check": decision.reason, "bitso": result}

    return application


app = create_app()
