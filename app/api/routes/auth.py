import secrets
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, Request
from fastapi.routing import APIRoute

from app.api.dependencies import (
    SESSION_AUTH_KEY,
    SESSION_USERNAME_KEY,
    SESSION_USER_ID_KEY,
    require_admin,
)
from app.api.routes.account import router as account_router
from app.api.routes.capital import router as capital_router
from app.api.routes.markets import router as markets_router
from app.api.routes.order_events import router as order_events_router
from app.api.routes.partial_closes import router as partial_closes_router
from app.api.routes.performance_summary import router as performance_summary_router
from app.models import LoginRequest, RegisterRequest
from app.repositories.users import OWNER_USER_ID, SqlUserAccountRepository


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
router.include_router(partial_closes_router)
router.include_router(performance_summary_router)
router.include_router(account_router)


def _start_session(request: Request, user) -> None:
    request.session.clear()
    request.session[SESSION_AUTH_KEY] = True
    request.session[SESSION_USER_ID_KEY] = user.id
    request.session[SESSION_USERNAME_KEY] = user.username


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    settings = request.app.state.settings
    username = (body.username or settings.owner_username).strip().lower()
    owner_username = settings.owner_username.strip().lower()

    # The owner password is managed by Render. Authenticate it before touching
    # PostgreSQL so a sleeping or unavailable database cannot block access to
    # the application shell. Database-backed family users continue below.
    if username == owner_username and secrets.compare_digest(
        body.password,
        settings.app_password,
    ):
        user = SimpleNamespace(id=OWNER_USER_ID, username=owner_username)
        _start_session(request, user)
        return {"ok": True}

    user = None
    try:
        with request.app.state.db_session_factory() as session:
            repository = SqlUserAccountRepository(session)
            user = repository.authenticate(username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="La base de datos está tardando o no está disponible. Intenta nuevamente en unos segundos.",
        ) from exc

    if user is None:
        detail = (
            "Contraseña incorrecta."
            if username == owner_username
            else "Usuario o contraseña incorrectos."
        )
        raise HTTPException(status_code=401, detail=detail)
    _start_session(request, user)
    return {"ok": True}


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, request: Request):
    settings = request.app.state.settings
    if not settings.registration_enabled:
        raise HTTPException(status_code=403, detail="El registro está desactivado.")
    if not secrets.compare_digest(
        body.registration_code,
        settings.user_registration_code,
    ):
        raise HTTPException(status_code=403, detail="Código familiar incorrecto.")

    with request.app.state.db_session_factory() as session:
        repository = SqlUserAccountRepository(session)
        repository.ensure_owner(
            username=settings.owner_username,
            display_name="Paul",
            password=settings.app_password,
            initial_capital_mxn=settings.simulated_initial_capital_mxn,
        )
        try:
            user = repository.create(
                username=body.username,
                display_name=body.display_name,
                password=body.password,
                initial_capital_mxn=settings.simulated_initial_capital_mxn,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        session.commit()
        session.refresh(user)
        public = user.to_public_dict()
        _start_session(request, user)
    return {
        "ok": True,
        "user": public,
        "message": "Cuenta creada con $5,000 MXN simulados y bot habilitado.",
    }


@router.get("/users")
async def list_users(request: Request):
    require_admin(request)
    with request.app.state.db_session_factory() as session:
        users = SqlUserAccountRepository(session).list_active()
    return {"items": users, "count": len(users)}


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}
