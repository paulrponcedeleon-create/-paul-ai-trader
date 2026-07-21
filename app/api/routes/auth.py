import secrets

from fastapi import APIRouter, HTTPException, Request

from app.api.dependencies import SESSION_AUTH_KEY
from app.api.routes.capital import router as capital_router
from app.api.routes.markets import router as markets_router
from app.models import LoginRequest

router = APIRouter(prefix="/api", tags=["auth"])
router.include_router(markets_router)
router.include_router(capital_router)


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
