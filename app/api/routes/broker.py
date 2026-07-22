from __future__ import annotations

from fastapi import APIRouter, Request

from app.brokers import BrokerFactory, BrokerInterface

router = APIRouter(tags=["broker"])


@router.post("/broker/connect")
async def broker_connect(request: Request):
    return _broker(request).connect().to_public_dict()


@router.post("/broker/disconnect")
async def broker_disconnect(request: Request):
    return _broker(request).disconnect().to_public_dict()


@router.get("/broker/status")
async def broker_status(request: Request):
    broker = _broker(request)
    return {"broker": broker.name, **broker.health().to_public_dict()}


@router.get("/broker/health")
async def broker_health(request: Request):
    return _broker(request).health().to_public_dict()


@router.get("/broker/balance")
async def broker_balance(request: Request):
    return _broker(request).get_balance().to_public_dict()


@router.get("/broker/positions")
async def broker_positions(request: Request):
    return {"items": _broker(request).get_positions()}


@router.get("/broker/orders")
async def broker_orders(request: Request):
    return {
        "items": [order.to_public_dict() for order in _broker(request).get_orders()]
    }


def _broker(request: Request) -> BrokerInterface:
    broker = getattr(request.app.state, "broker", None)
    if broker is None:
        broker = BrokerFactory(settings=request.app.state.settings).create()
        request.app.state.broker = broker
    return broker
