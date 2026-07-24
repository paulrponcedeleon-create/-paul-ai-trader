from fastapi import HTTPException, Request

from app.repositories.users import OWNER_USER_ID, SqlUserAccountRepository
from app.security.user_context import set_current_user_id

SESSION_AUTH_KEY = "authenticated"
SESSION_USER_ID_KEY = "user_id"
SESSION_USERNAME_KEY = "username"


def current_user_id(request: Request) -> str | None:
    if request.session.get(SESSION_AUTH_KEY) is not True:
        return None
    return str(request.session.get(SESSION_USER_ID_KEY) or OWNER_USER_ID)


def current_username(request: Request) -> str | None:
    if request.session.get(SESSION_AUTH_KEY) is not True:
        return None
    return str(request.session.get(SESSION_USERNAME_KEY) or "paul")


def authenticated(request: Request) -> bool:
    return current_user_id(request) is not None


def require_auth(request: Request) -> str:
    user_id = current_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Inicia sesión.")
    set_current_user_id(user_id)
    return user_id


def require_admin(request: Request) -> str:
    user_id = require_auth(request)
    with request.app.state.db_session_factory() as session:
        row = SqlUserAccountRepository(session).get_row(user_id)
        if row is None or not row.is_active:
            request.session.clear()
            raise HTTPException(status_code=401, detail="La cuenta ya no está activa.")
        if not row.is_admin:
            raise HTTPException(status_code=403, detail="Se requiere una cuenta administradora.")
    return user_id
