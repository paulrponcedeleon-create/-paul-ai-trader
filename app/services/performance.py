from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from zoneinfo import ZoneInfo

MONEY = Decimal("0.01")
PERCENT = Decimal("0.0001")
SUPPORTED_PERIODS = {"today", "7d", "30d", "month", "year", "all", "custom"}


def _decimal(value: Any | None) -> Decimal:
    return Decimal(str(value or 0))


def _money(value: Decimal) -> float:
    return float(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def _percent(value: Decimal) -> float:
    return float(value.quantize(PERCENT, rounding=ROUND_HALF_UP))


def resolve_period_range(
    period: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    timezone_name: str = "America/Ciudad_Juarez",
    now: datetime | None = None,
) -> tuple[datetime | None, datetime | None, str]:
    if period not in SUPPORTED_PERIODS:
        raise ValueError("Periodo no válido.")

    local_zone = ZoneInfo(timezone_name)
    local_now = (now or datetime.now(timezone.utc)).astimezone(local_zone)
    today = local_now.date()

    if period == "all":
        return None, None, "Todo el historial"

    if period == "custom":
        if start_date is None or end_date is None:
            raise ValueError("Selecciona fecha inicial y fecha final.")
        if end_date < start_date:
            raise ValueError("La fecha final no puede ser anterior a la inicial.")
        first_day = start_date
        last_day = end_date
        label = f"{first_day.isoformat()} a {last_day.isoformat()}"
    elif period == "today":
        first_day = today
        last_day = today
        label = "Hoy"
    elif period == "7d":
        first_day = today - timedelta(days=6)
        last_day = today
        label = "Últimos 7 días"
    elif period == "30d":
        first_day = today - timedelta(days=29)
        last_day = today
        label = "Últimos 30 días"
    elif period == "month":
        first_day = today.replace(day=1)
        last_day = today
        label = "Mes actual"
    else:
        first_day = today.replace(month=1, day=1)
        last_day = today
        label = "Año actual"

    start_local = datetime.combine(first_day, time.min, tzinfo=local_zone)
    end_local = datetime.combine(
        last_day + timedelta(days=1), time.min, tzinfo=local_zone
    )
    return (
        start_local.astimezone(timezone.utc),
        end_local.astimezone(timezone.utc),
        label,
    )


def summarize_closed_orders(
    orders: list[dict[str, Any]],
    *,
    timezone_name: str = "America/Ciudad_Juarez",
) -> dict[str, Any]:
    local_zone = ZoneInfo(timezone_name)
    by_day: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {
            "invested_mxn": Decimal("0"),
            "gross_pnl_mxn": Decimal("0"),
            "fees_mxn": Decimal("0"),
            "net_pnl_mxn": Decimal("0"),
            "operations": 0,
        }
    )
    by_book: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {
            "invested_mxn": Decimal("0"),
            "gross_pnl_mxn": Decimal("0"),
            "fees_mxn": Decimal("0"),
            "net_pnl_mxn": Decimal("0"),
            "operations": 0,
            "wins": 0,
            "losses": 0,
        }
    )

    total_invested = Decimal("0")
    total_fees = Decimal("0")
    net_pnl = Decimal("0")
    wins: list[Decimal] = []
    losses: list[Decimal] = []
    details: list[dict[str, Any]] = []

    for order in orders:
        amount = _decimal(order.get("amount_mxn"))
        entry_fee = _decimal(order.get("entry_fee_mxn"))
        exit_fee = _decimal(order.get("exit_fee_mxn"))
        fees = entry_fee + exit_fee
        realized = _decimal(order.get("realized_pnl_mxn"))
        gross = realized + fees
        book = str(order.get("book", "unknown")).lower()
        closed_at_raw = order.get("closed_at")
        closed_at = (
            datetime.fromisoformat(str(closed_at_raw))
            if closed_at_raw and not isinstance(closed_at_raw, datetime)
            else closed_at_raw
        )
        if closed_at is None:
            continue
        if closed_at.tzinfo is None:
            closed_at = closed_at.replace(tzinfo=timezone.utc)
        local_closed_at = closed_at.astimezone(local_zone)
        day_key = local_closed_at.date().isoformat()

        total_invested += amount
        total_fees += fees
        net_pnl += realized
        if realized > 0:
            wins.append(realized)
        elif realized < 0:
            losses.append(realized)

        day = by_day[day_key]
        day["invested_mxn"] += amount
        day["gross_pnl_mxn"] += gross
        day["fees_mxn"] += fees
        day["net_pnl_mxn"] += realized
        day["operations"] += 1

        book_row = by_book[book]
        book_row["invested_mxn"] += amount
        book_row["gross_pnl_mxn"] += gross
        book_row["fees_mxn"] += fees
        book_row["net_pnl_mxn"] += realized
        book_row["operations"] += 1
        if realized > 0:
            book_row["wins"] += 1
        elif realized < 0:
            book_row["losses"] += 1

        details.append(
            {
                "id": order.get("id"),
                "book": book,
                "side": order.get("side"),
                "closed_at": local_closed_at.isoformat(),
                "amount_mxn": _money(amount),
                "gross_pnl_mxn": _money(gross),
                "fees_mxn": _money(fees),
                "net_pnl_mxn": _money(realized),
                "return_pct": _percent((realized / amount) * Decimal("100"))
                if amount
                else 0.0,
            }
        )

    gross_pnl = net_pnl + total_fees
    total_operations = len(details)
    decisive_operations = len(wins) + len(losses)
    win_rate = (
        Decimal(len(wins)) / Decimal(decisive_operations) * Decimal("100")
        if decisive_operations
        else Decimal("0")
    )
    return_pct = (
        net_pnl / total_invested * Decimal("100") if total_invested else Decimal("0")
    )

    daily_rows = []
    cumulative = Decimal("0")
    for day_key in sorted(by_day):
        row = by_day[day_key]
        cumulative += row["net_pnl_mxn"]
        invested = row["invested_mxn"]
        daily_rows.append(
            {
                "date": day_key,
                "operations": row["operations"],
                "invested_mxn": _money(invested),
                "gross_pnl_mxn": _money(row["gross_pnl_mxn"]),
                "fees_mxn": _money(row["fees_mxn"]),
                "net_pnl_mxn": _money(row["net_pnl_mxn"]),
                "return_pct": _percent((row["net_pnl_mxn"] / invested) * Decimal("100"))
                if invested
                else 0.0,
                "cumulative_net_pnl_mxn": _money(cumulative),
            }
        )

    book_rows = []
    for book in sorted(by_book):
        row = by_book[book]
        invested = row["invested_mxn"]
        book_rows.append(
            {
                "book": book,
                "operations": row["operations"],
                "wins": row["wins"],
                "losses": row["losses"],
                "invested_mxn": _money(invested),
                "gross_pnl_mxn": _money(row["gross_pnl_mxn"]),
                "fees_mxn": _money(row["fees_mxn"]),
                "net_pnl_mxn": _money(row["net_pnl_mxn"]),
                "return_pct": _percent((row["net_pnl_mxn"] / invested) * Decimal("100"))
                if invested
                else 0.0,
            }
        )

    details.sort(key=lambda item: item["closed_at"], reverse=True)
    return {
        "summary": {
            "closed_operations": total_operations,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": _percent(win_rate),
            "invested_mxn": _money(total_invested),
            "gross_pnl_mxn": _money(gross_pnl),
            "fees_mxn": _money(total_fees),
            "net_pnl_mxn": _money(net_pnl),
            "return_pct": _percent(return_pct),
            "best_trade_mxn": _money(max(wins + losses)) if wins or losses else 0.0,
            "worst_trade_mxn": _money(min(wins + losses)) if wins or losses else 0.0,
            "average_win_mxn": _money(sum(wins, Decimal("0")) / len(wins))
            if wins
            else 0.0,
            "average_loss_mxn": _money(sum(losses, Decimal("0")) / len(losses))
            if losses
            else 0.0,
        },
        "daily": daily_rows,
        "by_book": book_rows,
        "operations": details,
    }
