from fastapi import HTTPException, Request

SESSION_AUTH_KEY = "authenticated"


def authenticated(request: Request) -> bool:
    return request.session.get(SESSION_AUTH_KEY) is True


def require_auth(request: Request) -> None:
    if not authenticated(request):
        raise HTTPException(status_code=401, detail="Inicia sesión.")
