from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import current_username, require_auth


router = APIRouter(tags=["mobile-lite"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[2] / "templates")
ALLOWED_TABS = {"overview", "markets", "paper", "strategies", "validation", "system"}


@router.get("/mobile", response_class=HTMLResponse)
async def mobile_lite(request: Request, tab: str = Query(default="overview")):
    require_auth(request)
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
        },
    )
