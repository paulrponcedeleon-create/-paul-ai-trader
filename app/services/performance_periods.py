from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from app.services.money import public_money, quantize_money, to_decimal


def period_bounds(
    now: datetime,
    period: str,
    timezone_name: str,
) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone_name)
    local_now = now.astimezone(zone)
    if period == "day":
        start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_local = (local_now - timedelta(days=local_now.weekday())).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    elif period == "month":
        start_local = local_now.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    else:
        raise ValueError("Periodo no soportado.")
    return start_local.astimezone(timezone.utc), local_now.astimezone(timezone.utc)


def summarize_closed_orders(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    total_pnl = Decimal("0.00")
    total_fees = Decimal("0.00")
    wins = 0
    losses = 0
    flat = 0
    by_book: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "realized_pnl_mxn": Decimal("0.00"),
            "fees_mxn": Decimal("0.00"),
            "trades": 0,
            "wins": 0,
            "losses": 0,
        }
    )

    for row in rows:
        pnl = quantize_money(row.get("realized_pnl_mxn") or 0)
        fees = quantize_money(
            to_decimal(row.get("entry_fee_mxn") or 0)
            + to_decimal(row.get("exit_fee_mxn") or 0)
        )
        book = str(row.get("book") or "unknown").lower()
        total_pnl += pnl
        total_fees += fees
        by_book[book]["realized_pnl_mxn"] += pnl
        by_book[book]["fees_mxn"] += fees
        by_book[book]["trades"] += 1
        if pnl > 0:
            wins += 1
            by_book[book]["wins"] += 1
        elif pnl < 0:
            losses += 1
            by_book[book]["losses"] += 1
        else:
            flat += 1

    trades = wins + losses + flat
    decided = wins + losses
    win_rate = (
        Decimal(wins) / Decimal(decided) * Decimal("100")
        if decided
        else Decimal("0")
    )
    books = [
        {
            "book": book,
            "realized_pnl_mxn": public_money(
                quantize_money(values["realized_pnl_mxn"])
            ),
            "fees_mxn": public_money(quantize_money(values["fees_mxn"])),
            "trades": values["trades"],
            "wins": values["wins"],
            "losses": values["losses"],
        }
        for book, values in sorted(by_book.items())
    ]
    return {
        "realized_pnl_mxn": public_money(quantize_money(total_pnl)),
        "fees_mxn": public_money(quantize_money(total_fees)),
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "flat": flat,
        "win_rate_pct": float(win_rate.quantize(Decimal("0.01"))),
        "by_book": books,
    }
