from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import authenticated, current_username


router = APIRouter(tags=["mobile-lite"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[2] / "templates")
ALLOWED_TABS = {"overview", "markets", "paper", "strategies", "validation", "system"}


@router.get("/mobile", response_class=HTMLResponse)
async def mobile_lite(request: Request, tab: str = Query(default="overview")):
    # A browser opening this URL without the session cookie should see the
    # normal login page, never a raw JSON authentication error.
    if not authenticated(request):
        return RedirectResponse(url="/", status_code=303)

    active_tab = tab if tab in ALLOWED_TABS else "overview"
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request=request,
        name="mobile_lite.html",
        context={
            "app_name": settings.app_name,
            "active_tab": active_tab,
            "current_username": current_username(request),
            "max_order": settings.max_order_mxn,
            "allowed_books": sorted(settings.allowed_books_set),
            "live_trading": settings.live_trading,
            "fallback_capital": float(settings.simulated_initial_capital_mxn),
        },
    )
