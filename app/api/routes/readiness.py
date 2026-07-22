from fastapi import APIRouter, Request, Response

from app.services.readiness import check_readiness

router = APIRouter(tags=["readiness"])


@router.get("/ready")
@router.get("/readiness")
async def ready(request: Request, response: Response):
    result = check_readiness(request.app.state.settings, request.app.state.db_engine)
    response.status_code = result.status_code
    return result.payload
