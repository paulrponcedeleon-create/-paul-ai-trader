from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import math
import statistics
from typing import Any, Iterable

from app.services.money import to_decimal
from app.services.trade_sources import (
    LEARNING_SOURCES,
    POSITION_SOURCES,
    infer_position_source,
    source_label,
)

_STRATEGY_NAMES = {
    "manual": "manual_paul",
    "runtime": "runtime_bot",
    "exploration": "exploration_ai",
}


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
        sharpe = statistics.fmean(returns) / deviation * math.sqrt(len(returns)) if deviation else 0.0
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
        source = infer_position_source(row)
        if source in LEARNING_SOURCES:
            grouped[source].append(row)
    return [
        _source_observation(source, grouped[source])
        for source in POSITION_SOURCES
        if grouped.get(source)
    ]


def learning_source_summary(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    counts = {source: 0 for source in POSITION_SOURCES}
    for row in rows:
        source = infer_position_source(row)
        if source in counts:
            counts[source] += 1
    return {
        "included_sources": list(POSITION_SOURCES),
        "manual_samples": counts["manual"],
        "runtime_samples": counts["runtime"],
        "exploration_samples": counts["exploration"],
        "bot_samples": counts["runtime"] + counts["exploration"],
        "total_samples": sum(counts.values()),
        "source_is_preserved": True,
    }
