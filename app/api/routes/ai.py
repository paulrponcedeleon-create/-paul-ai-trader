from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.ai import (
    AIDecisionEngine,
    DecisionRequest,
    HistoricalMetricsInput,
    IndicatorInput,
    PaperPortfolioInput,
    StrategySignalInput,
)
from app.services.signals import Signal

router = APIRouter(tags=["ai-decision"])


class SignalBody(BaseModel):
    strategy_name: str
    action: str
    confidence: int = Field(ge=0, le=100)
    reason: str = ""
    reference_price: float = 0
    weight: float = Field(default=1, ge=0)


class MetricsBody(BaseModel):
    total_return_pct: float = 0
    max_drawdown_pct: float = 0
    sharpe: float = 0
    profit_factor: float | None = None
    win_rate_pct: float = 0
    stability_pct: float = 50


class PortfolioBody(BaseModel):
    equity_mxn: float
    cash_mxn: float
    realized_pnl_mxn: float = 0
    unrealized_pnl_mxn: float = 0
    max_drawdown_pct: float = 0
    open_positions: int = 0


class IndicatorBody(BaseModel):
    closes: list[float] = Field(default_factory=list)
    highs: list[float] = Field(default_factory=list)
    lows: list[float] = Field(default_factory=list)
    volumes: list[float] = Field(default_factory=list)
    current: dict[str, float] = Field(default_factory=dict)


class EvaluateBody(BaseModel):
    strategy_signals: list[SignalBody]
    optimization_results: list[dict[str, Any]] = Field(default_factory=list)
    historical_metrics: MetricsBody = Field(default_factory=MetricsBody)
    paper_portfolio: PortfolioBody | None = None
    indicators: IndicatorBody = Field(default_factory=IndicatorBody)


@router.post("/ai/evaluate")
async def evaluate_ai(body: EvaluateBody, request: Request):
    decision = _engine(request).evaluate(_request(body))
    request.app.state.ai_last_decision = decision
    return decision.to_public_dict()


@router.get("/ai/decision")
async def get_ai_decision(request: Request):
    return _last(request).to_public_dict()


@router.get("/ai/explanation")
async def get_ai_explanation(request: Request):
    return _last(request).explanation.to_public_dict()


@router.get("/ai/confidence")
async def get_ai_confidence(request: Request):
    decision = _last(request)
    return {"confidence": decision.confidence, "score": float(decision.score)}


def _engine(request: Request) -> AIDecisionEngine:
    engine = getattr(request.app.state, "ai_decision_engine", None)
    if engine is None:
        engine = AIDecisionEngine()
        request.app.state.ai_decision_engine = engine
    return engine


def _last(request: Request):
    decision = getattr(request.app.state, "ai_last_decision", None)
    if decision is None:
        raise HTTPException(status_code=404, detail="No existe decisión AI evaluada.")
    return decision


def _request(body: EvaluateBody) -> DecisionRequest:
    signals = tuple(
        StrategySignalInput(
            strategy_name=item.strategy_name,
            signal=Signal(
                item.action.lower(), item.confidence, item.reason, item.reference_price
            ),
            weight=item.weight,
        )
        for item in body.strategy_signals
    )
    metrics = HistoricalMetricsInput(**body.historical_metrics.model_dump())
    portfolio = (
        PaperPortfolioInput(**body.paper_portfolio.model_dump())
        if body.paper_portfolio
        else None
    )
    indicator_input = IndicatorInput(
        closes=tuple(body.indicators.closes),
        highs=tuple(body.indicators.highs),
        lows=tuple(body.indicators.lows),
        volumes=tuple(body.indicators.volumes),
        current=body.indicators.current,
    )
    return DecisionRequest(
        signals, tuple(body.optimization_results), metrics, portfolio, indicator_input
    )
