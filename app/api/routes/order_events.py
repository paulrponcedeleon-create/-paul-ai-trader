from __future__ import annotations

from datetime import datetime, timezone
import os

from fastapi import APIRouter, Query, Request, Response

from app.api.dependencies import require_auth
from app.repositories.order_events import SqlSimulatedOrderEventRepository

router = APIRouter(tags=["orders"])


@router.get("/orders")
async def order_events(
    request: Request,
    response: Response,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    books: str | None = Query(default=None),
    side: str | None = Query(default=None, pattern="^(buy|sell)$"),
    source: str | None = Query(default=None),
):
    require_auth(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    selected_books = {
        item.strip().lower() for item in (books or "").split(",") if item.strip()
    }
    session_factory = request.app.state.db_session_factory
    with session_factory() as session:
        repository = SqlSimulatedOrderEventRepository(session)
        items = repository.list(
            limit=limit,
            offset=offset,
            books=selected_books or None,
            side=side,
            source=source,
        )
        total = repository.count(
            books=selected_books or None,
            side=side,
            source=source,
        )
    shown = offset + len(items)
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": shown < total,
        "next_offset": shown if shown < total else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/release")
async def release_info(request: Request):
    require_auth(request)
    commit = os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT") or "local"
    branch = os.getenv("RENDER_GIT_BRANCH") or "v2-dashboard"
    release = os.getenv("APP_RELEASE") or "Gate 1 · Contabilidad Decimal"
    return {
        "release": release,
        "branch": branch,
        "commit": commit[:8] if commit != "local" else commit,
        "mode": "live" if request.app.state.settings.live_trading else "simulation",
    }
