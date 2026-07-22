from __future__ import annotations

import csv
import io
import json
from typing import Any, Protocol

from app.optimization.ranking import RankingEngine


class _Rankable(Protocol):
    data: dict[str, Any]


def _public(report: Any) -> dict[str, Any]:
    return (
        report.to_public_dict() if hasattr(report, "to_public_dict") else dict(report)
    )


def optimization_summary(report: Any) -> str:
    data = _public(report)
    results = data.get("results", [])
    best = RankingEngine().top(list[_Rankable]([_Obj(item) for item in results]), 1)
    if not best:
        return "Optimización sin resultados."
    item = best[0].data
    return f"Optimización {data.get('status')} con {len(results)} resultados. Mejor score: {item.get('composite_score')}."


class _Obj:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        from decimal import Decimal

        self.total_return_pct = Decimal(str(data.get("total_return_pct", 0)))
        self.max_drawdown_pct = Decimal(str(data.get("max_drawdown_pct", 0)))
        self.sharpe = Decimal(str(data.get("sharpe", 0)))
        pf = data.get("profit_factor")
        self.profit_factor = None if pf is None else Decimal(str(pf))
        self.win_rate_pct = Decimal(str(data.get("win_rate_pct", 0)))
        self.composite_score = Decimal(str(data.get("composite_score", 0)))


def export_optimization_json(report: Any) -> str:
    data = _public(report)
    data["executive_summary"] = optimization_summary(report)
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def export_optimization_csv(report: Any) -> str:
    data = _public(report)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "rank",
            "strategy",
            "parameters",
            "return",
            "drawdown",
            "sharpe",
            "profit_factor",
            "win_rate",
            "trades",
            "score",
        ]
    )
    ranked = RankingEngine().rank(
        list[_Rankable]([_Obj(item) for item in data.get("results", [])])
    )
    for index, item in enumerate(ranked, start=1):
        row = item.data
        writer.writerow(
            [
                index,
                row.get("strategy_name"),
                json.dumps(row.get("parameters", {}), sort_keys=True),
                row.get("total_return_pct"),
                row.get("max_drawdown_pct"),
                row.get("sharpe"),
                row.get("profit_factor"),
                row.get("win_rate_pct"),
                row.get("trades_count"),
                row.get("composite_score"),
            ]
        )
    return output.getvalue()


def export_optimization_markdown(report: Any) -> str:
    data = _public(report)
    ranked = RankingEngine().rank(
        list[_Rankable]([_Obj(item) for item in data.get("results", [])])
    )
    lines = [
        "# Optimization Report",
        "",
        f"## Executive Summary\n\n{optimization_summary(report)}",
        "",
        "## Top 10",
    ]
    for index, item in enumerate(ranked[:10], start=1):
        row = item.data
        lines.append(
            f"{index}. score={row.get('composite_score')} return={row.get('total_return_pct')} params={row.get('parameters')}"
        )
    lines.extend(["", "## Bottom 10"])
    for index, item in enumerate(ranked[-10:], start=1):
        row = item.data
        lines.append(
            f"{index}. score={row.get('composite_score')} return={row.get('total_return_pct')} params={row.get('parameters')}"
        )
    return "\n".join(lines)
