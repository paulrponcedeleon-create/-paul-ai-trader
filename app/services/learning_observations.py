from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import math
import statistics
from typing import Any, Iterable

from app.services.money import public_money, quantize_money, to_decimal
from app.services.trade_sources import (
    BOT_SOURCES,
    LEARNING_SOURCES,
    MANUAL_SOURCE,
    POSITION_SOURCES,
    infer_position_source,
    public_source,
    source_label,
)

_STRATEGY_NAMES = {
    "manual": "manual_paul",
    "runtime": "runtime_bot",
    "exploration": "exploration_ai",
}
INITIAL_LEARNING_RESULTS = 100


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _source_observation(source: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl_values = [to_decimal(row.get("realized_pnl_mxn") or 0) for row in rows]
    amounts = [to_decimal(row.get("amount_mxn") or 0) for row in rows]
    returns = [
        float((pnl / amount) * Decimal("100")) if amount > 0 else 0.0
        for pnl, amount in zip(pnl_values, amounts)
    ]
    total_pnl = sum(pnl_values, Decimal("0"))
    total_amount = sum(amounts, Decimal("0"))
    observed_return = (
        float((total_pnl / total_amount) * Decimal("100"))
        if total_amount > 0
        else 0.0
    )

    cumulative = Decimal("0")
    peak = Decimal("0")
    max_drawdown = Decimal("0")
    for pnl in pnl_values:
        cumulative += pnl
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)
    drawdown_pct = (
        float((max_drawdown / total_amount) * Decimal("100"))
        if total_amount > 0
        else 0.0
    )

    wins = [value for value in pnl_values if value > 0]
    losses = [value for value in pnl_values if value < 0]
    decided = len(wins) + len(losses)
    win_rate = len(wins) / decided * 100 if decided else 0.0
    gross_profit = sum(wins, Decimal("0"))
    gross_loss = abs(sum(losses, Decimal("0")))
    profit_factor = (
        float(gross_profit / gross_loss)
        if gross_loss > 0
        else (999.0 if gross_profit > 0 else 0.0)
    )

    if len(returns) > 1:
        deviation = statistics.pstdev(returns)
        sharpe = (
            statistics.fmean(returns) / deviation * math.sqrt(len(returns))
            if deviation
            else 0.0
        )
        stability = 1.0 / (1.0 + deviation)
    else:
        sharpe = 0.0
        stability = 1.0 if returns else 0.0

    timestamps = [
        parsed
        for row in rows
        if (parsed := _parse_datetime(row.get("closed_at") or row.get("created_at")))
        is not None
    ]
    active_days = (
        max(1, (max(timestamps).date() - min(timestamps).date()).days + 1)
        if timestamps
        else 0
    )

    return {
        "strategy": _STRATEGY_NAMES[source],
        "source": source,
        "source_label": source_label(source),
        "observed_return_pct": observed_return,
        "drawdown_pct": drawdown_pct,
        "sharpe": sharpe,
        "profit_factor": profit_factor,
        "win_rate": win_rate,
        "trades": len(rows),
        "stability": stability,
        "active_days": active_days,
    }


def build_learning_observations(
    rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if str(row.get("status") or "").lower() != "closed":
            continue
        source = infer_position_source(row)
        if source in LEARNING_SOURCES:
            grouped[source].append(row)
    return [
        _source_observation(source, grouped[source])
        for source in POSITION_SOURCES
        if grouped.get(source)
    ]


def _source_summary(source: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    open_rows = [row for row in rows if str(row.get("status") or "").lower() == "open"]
    closed_rows = [
        row
        for row in rows
        if str(row.get("status") or "").lower() == "closed"
        and row.get("realized_pnl_mxn") is not None
    ]
    realized = sum(
        (to_decimal(row.get("realized_pnl_mxn") or 0) for row in closed_rows),
        Decimal("0"),
    )
    invested = sum(
        (to_decimal(row.get("amount_mxn") or 0) for row in open_rows),
        Decimal("0"),
    )
    wins = sum(to_decimal(row.get("realized_pnl_mxn") or 0) > 0 for row in closed_rows)
    losses = sum(to_decimal(row.get("realized_pnl_mxn") or 0) < 0 for row in closed_rows)
    flat = len(closed_rows) - wins - losses
    decided = wins + losses
    win_rate = wins / decided * 100 if decided else 0.0
    return {
        **public_source(source),
        "open_positions": len(open_rows),
        "closed_positions": len(closed_rows),
        "total_positions": len(open_rows) + len(closed_rows),
        "open_invested_mxn": public_money(quantize_money(invested)),
        "realized_pnl_mxn": public_money(quantize_money(realized)),
        "wins": wins,
        "losses": losses,
        "flat": flat,
        "win_rate_pct": round(win_rate, 2),
    }


def _combine_summaries(label: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    open_positions = sum(int(item["open_positions"]) for item in items)
    closed_positions = sum(int(item["closed_positions"]) for item in items)
    open_invested = sum(
        (to_decimal(item.get("open_invested_mxn") or 0) for item in items),
        Decimal("0"),
    )
    realized = sum(
        (to_decimal(item.get("realized_pnl_mxn") or 0) for item in items),
        Decimal("0"),
    )
    wins = sum(int(item["wins"]) for item in items)
    losses = sum(int(item["losses"]) for item in items)
    flat = sum(int(item["flat"]) for item in items)
    decided = wins + losses
    return {
        "label": label,
        "open_positions": open_positions,
        "closed_positions": closed_positions,
        "total_positions": open_positions + closed_positions,
        "open_invested_mxn": public_money(quantize_money(open_invested)),
        "realized_pnl_mxn": public_money(quantize_money(realized)),
        "wins": wins,
        "losses": losses,
        "flat": flat,
        "win_rate_pct": round(wins / decided * 100, 2) if decided else 0.0,
    }


def learning_source_summary(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        source = infer_position_source(row)
        if source in LEARNING_SOURCES:
            grouped[source].append(row)

    by_source = [
        _source_summary(source, grouped.get(source, []))
        for source in POSITION_SOURCES
    ]
    source_map = {item["source"]: item for item in by_source}
    manual = _combine_summaries(
        "Tus operaciones manuales",
        [source_map[MANUAL_SOURCE]],
    )
    bot = _combine_summaries(
        "Bot + IA",
        [source_map[source] for source in BOT_SOURCES],
    )
    all_sources = _combine_summaries("Total", by_source)
    completed = int(all_sources["closed_positions"])
    progress_pct = min(100.0, completed / INITIAL_LEARNING_RESULTS * 100)

    return {
        "included_sources": list(POSITION_SOURCES),
        "by_source": by_source,
        "comparison": {"manual": manual, "bot": bot},
        "manual_samples": int(source_map["manual"]["closed_positions"]),
        "runtime_samples": int(source_map["runtime"]["closed_positions"]),
        "exploration_samples": int(source_map["exploration"]["closed_positions"]),
        "bot_samples": int(bot["closed_positions"]),
        "total_samples": completed,
        "open_samples": int(all_sources["open_positions"]),
        "total_positions": int(all_sources["total_positions"]),
        "open_positions": int(all_sources["open_positions"]),
        "closed_positions": completed,
        "active_tracking_samples": int(all_sources["open_positions"]),
        "completed_result_samples": completed,
        "realized_pnl_mxn": all_sources["realized_pnl_mxn"],
        "learning_progress": {
            "completed_results": completed,
            "minimum_results": INITIAL_LEARNING_RESULTS,
            "percent": round(progress_pct, 2),
            "stage": "comparación inicial" if completed >= INITIAL_LEARNING_RESULTS else "recolección",
        },
        "source_is_preserved": True,
        "message": (
            "Las posiciones abiertas se siguen como contexto; solo las cerradas "
            "cuentan como resultados de ganancia o pérdida."
        ),
    }
