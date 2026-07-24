from datetime import datetime, timedelta, timezone
import inspect
import logging
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
from app.models import (
    LoginRequest,
    PasswordForgotRequest,
    PasswordResetRequest,
    RegisterRequest,
)
from app.repositories.users import OWNER_USER_ID, SqlUserAccountRepository
from app.services.password_recovery import (
    create_reset_token,
    hash_reset_token,
    send_password_reset_email,
)

logger = logging.getLogger(__name__)
_PASSWORD_RESET_MESSAGE = (
    "Si el correo está registrado, recibirás un enlace para crear una nueva contraseña."
)


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


def _ensure_owner(repository: SqlUserAccountRepository, settings) -> None:
    repository.ensure_owner(
        username=settings.owner_username,
        display_name="Paul",
        email=settings.owner_email,
        password=settings.app_password,
        initial_capital_mxn=settings.simulated_initial_capital_mxn,
    )


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    settings = request.app.state.settings
    username = (body.username or settings.owner_username).strip().lower()
    user = None
    try:
        with request.app.state.db_session_factory() as session:
            repository = SqlUserAccountRepository(session)
            _ensure_owner(repository, settings)
            session.commit()
            user = repository.authenticate(username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        # During the first rolling deploy the application may start before the
        # newest user migration is visible. Preserve only the original owner's
        # environment-password login; family accounts cannot use this path.
        if username == settings.owner_username.strip().lower() and secrets.compare_digest(
            body.password,
            settings.app_password,
        ):
            user = SimpleNamespace(id=OWNER_USER_ID, username=username)

    if user is None:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")
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
        _ensure_owner(repository, settings)
        try:
            user = repository.create(
                username=body.username,
                display_name=body.display_name,
                email=body.email,
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


@router.post("/password/forgot")
async def forgot_password(body: PasswordForgotRequest, request: Request):
    settings = request.app.state.settings
    custom_sender = getattr(request.app.state, "password_reset_sender", None)
    if not settings.smtp_configured and not callable(custom_sender):
        raise HTTPException(
            status_code=503,
            detail="El envío de correos todavía no está configurado.",
        )

    token = create_reset_token()
    token_hash = hash_reset_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_token_minutes
    )
    recipient = None
    display_name = None
    with request.app.state.db_session_factory() as session:
        repository = SqlUserAccountRepository(session)
        _ensure_owner(repository, settings)
        row = repository.issue_password_reset(
            body.email,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        session.commit()
        if row is not None:
            recipient = row.email
            display_name = row.display_name

    if recipient:
        reset_url = f"{str(request.base_url).rstrip('/')}?reset_token={token}"
        try:
            if callable(custom_sender):
                result = custom_sender(recipient, display_name, reset_url)
                if inspect.isawaitable(result):
                    await result
            else:
                await send_password_reset_email(
                    settings,
                    recipient,
                    display_name,
                    reset_url,
                )
        except Exception:
            # Do not expose whether the email exists. Operational failures stay in logs.
            logger.exception("Password reset email delivery failed")

    return {"ok": True, "message": _PASSWORD_RESET_MESSAGE}


@router.post("/password/reset")
async def reset_password(body: PasswordResetRequest, request: Request):
    with request.app.state.db_session_factory() as session:
        repository = SqlUserAccountRepository(session)
        user = repository.reset_password(
            token_hash=hash_reset_token(body.token),
            new_password=body.password,
        )
        if user is None:
            session.rollback()
            raise HTTPException(
                status_code=400,
                detail="El enlace es inválido, ya fue utilizado o venció.",
            )
        session.commit()
    request.session.clear()
    return {
        "ok": True,
        "message": "Contraseña actualizada. Ya puedes iniciar sesión.",
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
