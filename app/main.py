from datetime import datetime, timezone
from pathlib import Path
import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import Settings, settings
from app.models import LoginRequest, SimulatedOrderRequest
from app.services.bitso import BitsoClient, BitsoError
from app.services.risk import validate_order
from app.services.store import add_simulation, list_simulations
from app.services.strategy import momentum_signal

BASE_DIR = Path(__file__).resolve().parent
SESSION_AUTH_KEY = "authenticated"


def authenticated(request: Request) -> bool:
    return request.session.get(SESSION_AUTH_KEY) is True


def require_auth(request: Request) -> None:
    if not authenticated(request):
        raise HTTPException(status_code=401, detail="Inicia sesión.")


def create_app(
    app_settings: Settings | None = None,
    bitso_client: BitsoClient | None = None,
) -> FastAPI:
    current_settings = app_settings or settings
    current_bitso = bitso_client or BitsoClient(current_settings)

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

    @application.post("/api/login")
    async def login(body: LoginRequest, request: Request):
        if not secrets.compare_digest(body.password, current_settings.app_password):
            raise HTTPException(status_code=401, detail="Contraseña incorrecta.")
        request.session.clear()
        request.session[SESSION_AUTH_KEY] = True
        return {"ok": True}

    @application.post("/api/logout")
    async def logout(request: Request):
        request.session.clear()
        return {"ok": True}

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
        try:
            result = await current_bitso.ticker(book)
            ticker = result.get("payload", result)
            signal = momentum_signal(
                last=float(ticker["last"]),
                high=float(ticker["high"]),
                low=float(ticker["low"]),
                volume=float(ticker.get("volume", 0)),
            )
            return {
                "book": book,
                "ticker": ticker,
                "signal": signal.__dict__,
                "warning": "Señal educativa; no garantiza ganancias.",
            }
        except (BitsoError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @application.get("/api/balance")
    async def balance(request: Request):
        require_auth(request)
        try:
            return await current_bitso.balance()
        except BitsoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/simulations")
    async def simulations(request: Request):
        require_auth(request)
        return {"items": list_simulations()}

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
            item = {
                "id": secrets.token_hex(6),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "simulated",
                "book": body.book.lower(),
                "side": body.side,
                "amount_mxn": round(body.amount_mxn, 2),
                "risk_check": decision.reason,
            }
            return add_simulation(item)

        try:
            result = await current_bitso.place_market_order(
                body.book.lower(), body.side, body.amount_mxn
            )
        except BitsoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "submitted", "risk_check": decision.reason, "bitso": result}

    return application


app = create_app()
