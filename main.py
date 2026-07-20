from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .bitso import BitsoClient, BitsoError
from .config import settings
from .risk import validate_order
from .strategy import analyze_ticker

app = FastAPI(title="Paul AI Trader", version="0.2.0")
bitso = BitsoClient()
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

class OrderRequest(BaseModel):
    book: str = "btc_mxn"
    side: str = Field(pattern="^(buy|sell)$")
    amount_mxn: float = Field(gt=0)
    daily_pnl_mxn: float = 0
    open_orders: int = 0
    approved: bool = False

@app.get("/")
async def dashboard():
    return FileResponse(static_dir / "index.html")

@app.get("/api/status")
async def status():
    return {
        "mode": "LIVE" if settings.live_trading else "SIMULATION",
        "base_url": settings.bitso_base_url,
        "allowed_books": sorted(settings.allowed_books_set),
        "limits": {
            "max_order_mxn": settings.max_order_mxn,
            "max_daily_loss_mxn": settings.max_daily_loss_mxn,
            "max_open_orders": settings.max_open_orders,
            "manual_approval": settings.require_manual_approval,
        },
    }

@app.get("/api/market/{book}")
async def market(book: str):
    book = book.lower()
    if book not in settings.allowed_books_set:
        raise HTTPException(403, "Mercado no autorizado.")
    try:
        response = await bitso.ticker(book)
        p = response["payload"]
        signal = analyze_ticker(
            last=float(p["last"]), high=float(p["high"]), low=float(p["low"]),
            volume=float(p.get("volume", 0)), bid=float(p.get("bid", 0)), ask=float(p.get("ask", 0)),
        )
        return {"book": book, "ticker": p, "signal": signal.dict(), "warning": "No garantiza ganancias."}
    except (BitsoError, KeyError, ValueError) as exc:
        raise HTTPException(502, str(exc)) from exc

@app.get("/api/books")
async def books():
    try:
        return await bitso.available_books()
    except BitsoError as exc:
        raise HTTPException(502, str(exc)) from exc

@app.get("/api/account/balance")
async def balance():
    try:
        return await bitso.balance()
    except BitsoError as exc:
        raise HTTPException(400, str(exc)) from exc

@app.get("/api/account/open-orders")
async def open_orders(book: str | None = None):
    try:
        return await bitso.open_orders(book)
    except BitsoError as exc:
        raise HTTPException(400, str(exc)) from exc

@app.post("/api/orders")
async def order(req: OrderRequest):
    decision = validate_order(req.book, req.side, req.amount_mxn, req.daily_pnl_mxn,
                              req.open_orders, req.approved)
    if not decision.allowed:
        raise HTTPException(403, decision.reason)

    if not settings.live_trading:
        return {"status": "simulated", "request": req.model_dump(), "risk_check": decision.reason}

    try:
        result = await bitso.place_market_order(req.book, req.side, req.amount_mxn)
        return {"status": "submitted", "risk_check": decision.reason, "bitso": result}
    except BitsoError as exc:
        raise HTTPException(400, str(exc)) from exc
