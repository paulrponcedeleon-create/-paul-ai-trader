from datetime import datetime, timezone
from pathlib import Path
import secrets

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.models import LoginRequest, SimulatedOrderRequest
from app.services.bitso import BitsoClient, BitsoError
from app.services.risk import validate_order
from app.services.store import add_simulation, list_simulations
from app.services.strategy import momentum_signal

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title=settings.app_name, version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
bitso = BitsoClient()

SESSION_COOKIE = "paul_ai_session"
VALID_SESSION = secrets.token_urlsafe(24)

def authenticated(request: Request) -> bool:
    return request.cookies.get(SESSION_COOKIE) == VALID_SESSION

def require_auth(request: Request) -> None:
    if not authenticated(request):
        raise HTTPException(status_code=401, detail="Inicia sesión.")

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "mode": "live" if settings.live_trading else "simulation"}

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.app_name,
            "authenticated": authenticated(request),
            "live_trading": settings.live_trading,
            "max_order": settings.max_order_mxn,
            "allowed_books": sorted(settings.allowed_books_set),
        },
    )

@app.post("/api/login")
async def login(body: LoginRequest, response: Response):
    if not secrets.compare_digest(body.password, settings.app_password):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta.")
    response.set_cookie(
        SESSION_COOKIE,
        VALID_SESSION,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return {"ok": True}

@app.post("/api/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}

@app.get("/api/config")
async def config(request: Request):
    require_auth(request)
    return {
        "mode": "LIVE" if settings.live_trading else "SIMULATION",
        "allowed_books": sorted(settings.allowed_books_set),
        "max_order_mxn": settings.max_order_mxn,
        "max_daily_loss_mxn": settings.max_daily_loss_mxn,
        "max_open_orders": settings.max_open_orders,
        "bitso_connected": bool(settings.bitso_api_key and settings.bitso_api_secret),
    }

@app.get("/api/market/{book}")
async def market(book: str, request: Request):
    require_auth(request)
    book = book.lower()
    if book not in settings.allowed_books_set:
        raise HTTPException(status_code=403, detail="Mercado no autorizado.")
    try:
        result = await bitso.ticker(book)
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

@app.get("/api/balance")
async def balance(request: Request):
    require_auth(request)
    try:
        return await bitso.balance()
    except BitsoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/simulations")
async def simulations(request: Request):
    require_auth(request)
    return {"items": list_simulations()}

@app.post("/api/orders")
async def order(body: SimulatedOrderRequest, request: Request):
    require_auth(request)
    decision = validate_order(
        body.book, body.side, body.amount_mxn, body.daily_pnl_mxn, body.open_orders
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)

    if not settings.live_trading:
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
        result = await bitso.place_market_order(
            body.book.lower(), body.side, body.amount_mxn
        )
    except BitsoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "submitted", "risk_check": decision.reason, "bitso": result}
