from fastapi import APIRouter, Request, Response

from app.api.dependencies import require_auth
from app.repositories.simulated_orders import SqlSimulatedOrderRepository

router = APIRouter(tags=["capital"])


@router.get("/capital")
async def capital(request: Request, response: Response):
    require_auth(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    settings = request.app.state.settings
    session_factory = request.app.state.db_session_factory
    with session_factory() as db_session:
        repository = SqlSimulatedOrderRepository(db_session)
        return repository.capital_ledger(settings.simulated_initial_capital_mxn)
