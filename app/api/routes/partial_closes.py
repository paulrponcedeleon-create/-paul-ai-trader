from __future__ import annotations

from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, HTTPException, Request

from app.api.dependencies import require_auth
from app.models import PartialCloseRequest
from app.repositories.order_events import SqlSimulatedOrderEventRepository
from app.repositories.simulated_orders import SqlSimulatedOrderRepository
from app.services.bitso import BitsoError
from app.services.money import quantize_money, quantize_price, quantize_rate
from app.services.portfolio import calculate_position
from app.services.unified_markets import UnifiedMarketError, UnifiedMarketService

router = APIRouter(tags=["portfolio"])


def _market_service(request: Request) -> UnifiedMarketService:
    service = getattr(request.app.state, "unified_markets", None)
    if service is None:
        service = UnifiedMarketService(request.app.state.bitso)
        request.app.state.unified_markets = service
    return service


@router.post("/simulations/{simulation_id}/partial-close")
async def partial_close(
    simulation_id: str,
    body: PartialCloseRequest,
    request: Request,
):
    require_auth(request)
    if body.amount_mxn is None:
        raise HTTPException(status_code=422, detail="Indica el monto que deseas vender.")

    requested_amount = quantize_money(body.amount_mxn)
    session_factory = request.app.state.db_session_factory
    with session_factory() as session:
        repository = SqlSimulatedOrderRepository(session)
        open_order = repository.get_open(simulation_id)

    if open_order is None:
        raise HTTPException(
            status_code=404,
            detail="La posición no existe o ya fue cerrada.",
        )

    open_amount = quantize_money(open_order["amount_mxn"])
    if requested_amount >= open_amount:
        raise HTTPException(
            status_code=422,
            detail="Para vender todo utiliza Cerrar posición.",
        )

    try:
        quote = await _market_service(request).quote(
            str(open_order["book"]), force=True, side="sell"
        )
    except (UnifiedMarketError, BitsoError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    exit_fee_rate = quantize_rate(quote["effective_fee_rate"])
    close_price = quantize_price(quote["last"])
    partial_order = {**open_order, "amount_mxn": requested_amount}
    calculated = calculate_position(
        partial_order,
        close_price,
        exit_fee_rate=exit_fee_rate,
    )
    exit_fee = quantize_money(calculated["estimated_exit_fee_mxn"])
    realized_pnl = quantize_money(calculated["unrealized_pnl_mxn"])
    closed_at = datetime.now(timezone.utc)
    closed_lot_id = f"lot_{secrets.token_hex(6)}"

    with session_factory() as session:
        repository = SqlSimulatedOrderRepository(session)
        event_repository = SqlSimulatedOrderEventRepository(session)
        try:
            result = repository.close_partial(
                simulation_id,
                closed_lot_id=closed_lot_id,
                amount_mxn=requested_amount,
                closed_at=closed_at,
                close_price=close_price,
                exit_fee_rate=exit_fee_rate,
                exit_fee_mxn=exit_fee,
                realized_pnl_mxn=realized_pnl,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=409, detail="La posición ya fue cerrada.")
        closed_lot, remaining_position = result
        event_repository.add(
            {
                "id": f"evt_{secrets.token_hex(8)}",
                "created_at": closed_at,
                "position_id": closed_lot_id,
                "book": open_order["book"],
                "side": "sell",
                "status": "filled",
                "amount_mxn": requested_amount,
                "price": close_price,
                "fee_mxn": exit_fee,
                "realized_pnl_mxn": realized_pnl,
                "source": "manual",
                "reason": "manual_partial_close",
                "correlation_id": simulation_id,
            }
        )
        session.commit()

    return {
        "status": "partially_closed",
        "closed_lot": closed_lot,
        "remaining_position": remaining_position,
        "realized_pnl_mxn": float(realized_pnl),
        "fee_mxn": float(exit_fee),
    }
