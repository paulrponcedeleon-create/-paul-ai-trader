from fastapi import APIRouter, Request, Response

from app.api.dependencies import require_auth
from app.repositories.simulated_orders import SqlSimulatedOrderRepository
from app.services.current_account import user_initial_capital_mxn

router = APIRouter(tags=["capital"])


@router.get("/capital")
async def capital(request: Request, response: Response):
    user_id = require_auth(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    initial_capital = user_initial_capital_mxn(request, user_id)
    with request.app.state.db_session_factory() as db_session:
        repository = SqlSimulatedOrderRepository(db_session, user_id=user_id)
        result = repository.capital_ledger(initial_capital)
    return {"user_id": user_id, **result}
