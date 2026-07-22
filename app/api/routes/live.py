from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Query, Request

from app.brokers import BrokerFactory, BrokerInterface
from app.live import (
    ExecutionAuditLog,
    LiveOrderRequest,
    LiveTradingArmState,
    LiveTradingGuard,
)
from app.live.reports import (
    export_audit_report,
    export_guard_report,
)

router = APIRouter(tags=["live"])


@router.get("/live/status")
async def live_status(request: Request):
    settings = request.app.state.settings
    broker = _broker(request)
    status = {
        "live_trading": bool(settings.live_trading),
        "armed": _arm_state(request).armed,
        "broker": broker.name,
        "broker_health": broker.health().to_public_dict(),
        "default_is_paper_when_disabled": not bool(settings.live_trading),
    }
    return status


@router.get("/live/guards")
async def live_guards(request: Request):
    return export_guard_report(_guard(request).evaluate())


@router.post("/live/arm")
async def live_arm(request: Request, token: str = Query(..., min_length=8)):
    _arm_state(request).arm(token)
    return {"armed": True}


@router.post("/live/disarm")
async def live_disarm(request: Request):
    _arm_state(request).disarm()
    return {"armed": False}


@router.post("/live/validate")
async def live_validate(payload: dict[str, Any], request: Request):
    order = LiveOrderRequest(
        str(payload.get("book", "btc_mxn")).lower(),
        "sell" if payload.get("side") == "sell" else "buy",
        "limit" if payload.get("order_type") == "limit" else "market",
        Decimal(str(payload.get("amount_mxn", "0"))),
        Decimal(str(payload["price"])) if payload.get("price") is not None else None,
        str(payload.get("user", "system")),
        payload.get("strategy"),
        payload.get("ai_decision"),
        payload.get("confidence"),
    )
    return (
        _guard(request)
        .evaluate(order, confirmation_token=payload.get("confirmation_token"))
        .to_public_dict()
    )


@router.get("/live/audit")
async def live_audit(
    request: Request, limit: int = Query(100, ge=0), offset: int = Query(0, ge=0)
):
    return export_audit_report(_audit(request).list(limit=limit, offset=offset))


def _audit(request: Request) -> ExecutionAuditLog:
    audit = getattr(request.app.state, "live_audit_log", None)
    if audit is None:
        audit = ExecutionAuditLog()
        request.app.state.live_audit_log = audit
    return audit


def _arm_state(request: Request) -> LiveTradingArmState:
    state = getattr(request.app.state, "live_arm_state", None)
    if state is None:
        state = LiveTradingArmState()
        request.app.state.live_arm_state = state
    return state


def _broker(request: Request) -> BrokerInterface:
    broker = getattr(request.app.state, "broker", None)
    if broker is None:
        broker = BrokerFactory(settings=request.app.state.settings).create()
        request.app.state.broker = broker
    return broker


def _guard(request: Request) -> LiveTradingGuard:
    return LiveTradingGuard(
        settings=request.app.state.settings,
        broker=_broker(request),
        arm_state=_arm_state(request),
    )
