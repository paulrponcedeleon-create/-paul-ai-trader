from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfoNotFoundError

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.dependencies import require_auth
from app.repositories.simulated_orders import SqlSimulatedOrderRepository
from app.services.performance_periods import period_bounds, summarize_closed_orders

router = APIRouter(tags=["performance"])


@router.get("/performance/summary")
async def performance_summary(
    request: Request,
    books: str | None = Query(default=None),
    timezone_name: str = Query(default="America/Chihuahua", alias="timezone"),
):
    require_auth(request)
    selected_books = {
        item.strip().lower()
        for item in (books or "").split(",")
        if item.strip()
    }
    now = datetime.now(timezone.utc)
    session_factory = request.app.state.db_session_factory
    periods = {}
    try:
        with session_factory() as session:
            repository = SqlSimulatedOrderRepository(session)
            for period in ("day", "week", "month"):
                start_at, end_at = period_bounds(now, period, timezone_name)
                rows = repository.list_closed(
                    start_at=start_at,
                    end_at=end_at,
                    books=selected_books or None,
                )
                periods[period] = {
                    "start_at": start_at.isoformat(),
                    "end_at": end_at.isoformat(),
                    **summarize_closed_orders(rows),
                }
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Zona horaria no válida.") from exc

    return {
        "timezone": timezone_name,
        "books": sorted(selected_books),
        "periods": periods,
        "updated_at": now.isoformat(),
    }
