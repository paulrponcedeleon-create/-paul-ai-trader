from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api.dependencies import (
    authenticated,
    current_user_id,
    current_username,
    require_auth,
)
from app.api.routes.account import user_bitso_balance
from app.api.routes.adaptive import router as adaptive_router
from app.api.routes.ai import router as ai_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.auth import router as auth_router
from app.api.routes.broker import router as broker_router
from app.api.routes.burnin import router as burnin_router
from app.api.routes.experiments import router as experiments_router
from app.api.routes.live import router as live_router
from app.api.routes.market_data import router as market_data_router
from app.api.routes.optimization import router as optimization_router
from app.api.routes.paper import router as paper_router
from app.api.routes.pro_strategy import router as pro_strategy_router
from app.api.routes.readiness import router as readiness_router
from app.api.routes.research import router as research_router
from app.api.routes.runtime import router as runtime_router
from app.api.routes.runtime import shutdown_runtime, startup_runtime
from app.api.routes.system import router as system_router
from app.api.routes.validation import router as validation_router
from app.config import Settings, settings
from app.db import models as _models  # noqa: F401
from app.db import order_models as _order_models  # noqa: F401
from app.db import user_models as _user_models  # noqa: F401
from app.db.base import Base
from app.db.session import build_engine, build_session_factory
from app.repositories.simulated_orders import SqlSimulatedOrderRepository
from app.repositories.users import SqlUserAccountRepository
from app.services.bitso import BitsoClient
from app.services.performance import resolve_period_range, summarize_closed_orders
from app.services.store import list_simulations

BASE_DIR = Path(__file__).resolve().parent
PERFORMANCE_TIMEZONE = "America/Ciudad_Juarez"


def create_app(
    app_settings: Settings | None = None,
    bitso_client: BitsoClient | None = None,
) -> FastAPI:
    current_settings = app_settings or settings
    current_bitso = bitso_client or BitsoClient(current_settings)
    engine = build_engine(current_settings)
    session_factory = build_session_factory(engine)

    if current_settings.app_env == "test":
        Base.metadata.create_all(bind=engine)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.owner_bootstrap_error = None
        try:
            with session_factory() as session:
                SqlUserAccountRepository(session).ensure_owner(
                    username=current_settings.owner_username,
                    display_name="Paul",
                    password=current_settings.app_password,
                    initial_capital_mxn=current_settings.simulated_initial_capital_mxn,
                )
                session.commit()
        except Exception as exc:
            application.state.owner_bootstrap_error = f"{type(exc).__name__}: {exc}"

        try:
            await startup_runtime(application)
            yield
        finally:
            try:
                await shutdown_runtime(application)
            finally:
                engine.dispose()

    application = FastAPI(
        title=current_settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
    )
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

    def template_context(request: Request) -> dict:
        user_id = current_user_id(request)
        user = None
        if user_id:
            try:
                with session_factory() as session:
                    user = SqlUserAccountRepository(session).get_by_id(user_id)
            except Exception:
                user = None
        return {
            "app_name": current_settings.app_name,
            "authenticated": authenticated(request),
            "current_user": user,
            "current_username": current_username(request),
            "registration_enabled": current_settings.registration_enabled,
            "live_trading": current_settings.live_trading,
            "max_order": current_settings.max_order_mxn,
            "allowed_books": sorted(current_settings.allowed_books_set),
        }

    @application.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "mode": "live" if current_settings.live_trading else "simulation",
            "multiuser": True,
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
        user_id = require_auth(request)
        with session_factory() as session:
            user = SqlUserAccountRepository(session).get_row(user_id)
            if user is None:
                raise HTTPException(status_code=401, detail="Cuenta no disponible.")
            return {
                "mode": "LIVE" if current_settings.live_trading else "SIMULATION",
                "allowed_books": sorted(current_settings.allowed_books_set),
                "max_order_mxn": current_settings.max_order_mxn,
                "max_daily_loss_mxn": current_settings.max_daily_loss_mxn,
                "max_open_orders": current_settings.max_open_orders,
                "simulated_initial_capital_mxn": float(
                    user.simulated_initial_capital_mxn
                ),
                "bot_enabled": user.bot_enabled,
                "ai_exploration_enabled": user.ai_exploration_enabled,
                "shared_learning_enabled": user.shared_learning_enabled,
                "bitso_connected": bool(
                    user.bitso_api_key_encrypted and user.bitso_api_secret_encrypted
                ),
                "user": user.to_public_dict(),
            }

    @application.get("/api/balance")
    async def balance(request: Request):
        return await user_bitso_balance(request)

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
                status_code=403,
                detail="Una o más criptomonedas no están autorizadas.",
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

    return application


app = create_app()
