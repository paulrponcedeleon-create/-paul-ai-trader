from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.analytics import AnalyticsEvent, AnalyticsService, TradeAnalytics

router = APIRouter(tags=["analytics"])


@router.get("/analytics/status")
async def analytics_status(request: Request):
    return {
        "status": "ready",
        "trades": len(_trades(request)),
        "events": len(_events(request)),
    }


@router.get("/analytics/summary")
async def analytics_summary(
    request: Request,
    start: datetime | None = None,
    end: datetime | None = None,
    asset: str | None = None,
    strategy: str | None = None,
    broker: str | None = None,
    ai_decision: str | None = None,
    close_reason: str | None = None,
):
    trades = _filtered(
        request,
        start=start,
        end=end,
        asset=asset,
        strategy=strategy,
        broker=broker,
        ai_decision=ai_decision,
        close_reason=close_reason,
    )
    return _service(request).summary(trades).to_public_dict()


@router.get("/analytics/performance")
async def analytics_performance(request: Request):
    return await analytics_summary(request)


@router.get("/analytics/equity")
async def analytics_equity(request: Request, period: str = "trade"):
    return {
        "period": period,
        "items": [
            item.to_public_dict() for item in _service(request).equity(_trades(request))
        ],
    }


@router.get("/analytics/drawdown")
async def analytics_drawdown(request: Request):
    return {
        "items": [
            item.to_public_dict()
            for item in _service(request).drawdown(_trades(request))
        ]
    }


@router.get("/analytics/strategies")
async def analytics_strategies(request: Request):
    return {
        "items": [
            item.to_public_dict()
            for item in _service(request).strategies(_trades(request))
        ]
    }


@router.get("/analytics/assets")
async def analytics_assets(request: Request):
    return {
        "items": [
            item.to_public_dict() for item in _service(request).assets(_trades(request))
        ]
    }


@router.get("/analytics/ai")
async def analytics_ai(request: Request):
    return {
        "items": [
            item.to_public_dict()
            for item in _service(request).ai(_trades(request), _events(request))
        ]
    }


@router.get("/analytics/risk")
async def analytics_risk(request: Request):
    return _service(request).risk(_trades(request), _events(request)).to_public_dict()


@router.get("/analytics/broker")
async def analytics_broker(request: Request):
    return _service(request).broker(_events(request)).to_public_dict()


@router.get("/analytics/time")
async def analytics_time(request: Request, period: str = "day"):
    return {
        "period": period,
        "items": [
            item.to_public_dict()
            for item in _service(request).time(_trades(request), period)
        ],
    }


@router.get("/analytics/trades")
async def analytics_trades(
    request: Request, limit: int = Query(100, ge=0), offset: int = Query(0, ge=0)
):
    return {
        "items": [
            trade.to_public_dict()
            for trade in _trades(request)[offset : offset + limit]
        ]
    }


@router.get("/analytics/events")
async def analytics_events(
    request: Request,
    category: str | None = None,
    severity: str | None = None,
    limit: int = Query(100, ge=0),
    offset: int = Query(0, ge=0),
):
    events = [
        e
        for e in _events(request)
        if (category is None or e.category == category)
        and (severity is None or e.severity == severity)
    ]
    return {
        "items": [event.to_public_dict() for event in events[offset : offset + limit]]
    }


@router.post("/analytics/snapshot")
async def analytics_snapshot(request: Request, period: str = "custom"):
    summary = _service(request).summary(_trades(request)).to_public_dict()
    if not hasattr(request.app.state, "db_session_factory"):
        return {"period": period, "metrics": summary, "persisted": False}
    try:
        from app.repositories.analytics import AnalyticsRepository

        with request.app.state.db_session_factory() as session:
            row = AnalyticsRepository(session).save_snapshot(
                period=period, metrics=summary
            )
            session.commit()
            return {"snapshot": row, "persisted": True}
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Persistencia analítica no disponible."
        ) from exc


def _service(request: Request) -> AnalyticsService:
    return AnalyticsService(broker=getattr(request.app.state, "broker", None))


def _trades(request: Request) -> list[TradeAnalytics]:
    return list(getattr(request.app.state, "analytics_trades", []))


def _events(request: Request) -> list[AnalyticsEvent]:
    return list(getattr(request.app.state, "analytics_events", []))


def _filtered(request: Request, **filters: Any) -> list[TradeAnalytics]:
    return AnalyticsService().performance_engine.filter_trades(
        _trades(request), **filters
    )
