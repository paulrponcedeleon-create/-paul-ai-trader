import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.routing import APIRoute

from app.api.dependencies import SESSION_AUTH_KEY
from app.api.routes.capital import router as capital_router
from app.api.routes.markets import router as markets_router
from app.api.routes.order_events import router as order_events_router
from app.models import LoginRequest


def _market_operation_id(route: APIRoute) -> str:
    methods = "_".join(sorted(method.lower() for method in route.methods or {"get"}))
    normalized_path = (
        route.path_format.strip("/")
        .replace("/", "_")
        .replace("{", "")
        .replace("}", "")
    )
    return f"unified_market_{route.name}_{normalized_path}_{methods}"


router = APIRouter(prefix="/api", tags=["auth"])
router.include_router(
    markets_router,
    generate_unique_id_function=_market_operation_id,
)
router.include_router(capital_router)
router.include_router(order_events_router)


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    settings = request.app.state.settings
    if not secrets.compare_digest(body.password, settings.app_password):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta.")

    request.session.clear()
    request.session[SESSION_AUTH_KEY] = True
    return {"ok": True}


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}
