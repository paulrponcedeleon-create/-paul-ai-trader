from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.paper_trading import PaperTradingEngine, PaperTradingRequest, PortfolioManager
from app.repositories.paper_trading import PaperTradingRepository

router = APIRouter(tags=["paper-trading"])


class PaperStartRequest(BaseModel):
    account_id: str = "default"
    book: str
    strategy_name: str
    strategy_version: str = "1.0"
    parameters: dict[str, Any] = Field(default_factory=dict)
    initial_cash_mxn: float = Field(default=10000, gt=0)
    fee_rate: float = Field(default=0.001, ge=0)
    sizing_method: str = "fixed_size"
    sizing_value: float = Field(default=1000, gt=0)


@router.post("/paper/start")
async def start_paper(body: PaperStartRequest, request: Request):
    with request.app.state.db_session_factory() as session:
        engine = PaperTradingEngine(
            portfolio=PortfolioManager(initial_cash_mxn=body.initial_cash_mxn),
            repository=PaperTradingRepository(session),
        )
        status = engine.start(
            PaperTradingRequest(
                account_id=body.account_id,
                book=body.book,
                strategy_name=body.strategy_name,
                strategy_version=body.strategy_version,
                parameters=body.parameters,
                fee_rate=body.fee_rate,
                sizing_method=body.sizing_method,
                sizing_value=body.sizing_value,
            )
        )
        session.commit()
        # Keep a safe in-memory engine after persistence. The repository created
        # above belongs to the request-scoped DB session and must not be reused.
        engine.repository = None
        request.app.state.paper_engine = engine
        return status.__dict__


@router.post("/paper/stop")
async def stop_paper(request: Request):
    engine = _engine(request)
    return engine.stop().__dict__


@router.get("/paper/status")
async def paper_status(request: Request):
    return _engine(request).status().__dict__


@router.get("/paper/portfolio")
async def paper_portfolio(request: Request):
    return _engine(request).portfolio.snapshot().to_public_dict()


@router.get("/paper/positions")
async def paper_positions(request: Request):
    return [
        position.__dict__ for position in _engine(request).portfolio.positions.values()
    ]


@router.get("/paper/orders")
async def paper_orders(request: Request):
    return [order.__dict__ for order in _engine(request).portfolio.orders]


@router.get("/paper/history")
async def paper_history(request: Request):
    return [trade.to_public_dict() for trade in _engine(request).portfolio.trades]


@router.post("/paper/reset")
async def paper_reset(request: Request):
    if hasattr(request.app.state, "paper_engine"):
        delattr(request.app.state, "paper_engine")
    return {"reset": True}


def _engine(request: Request) -> PaperTradingEngine:
    engine = getattr(request.app.state, "paper_engine", None)
    if engine is None:
        settings = request.app.state.settings
        engine = PaperTradingEngine(
            portfolio=PortfolioManager(
                initial_cash_mxn=float(
                    getattr(settings, "simulated_initial_capital_mxn", 1000.0)
                )
            )
        )
        request.app.state.paper_engine = engine
    return engine
