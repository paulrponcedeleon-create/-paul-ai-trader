from __future__ import annotations

import csv
import io
import json
from typing import Any


def _public_result(result: Any) -> dict[str, Any]:
    return (
        result.to_public_dict() if hasattr(result, "to_public_dict") else dict(result)
    )


def executive_summary(result: Any) -> str:
    data = _public_result(result)
    metrics = data.get("metrics") or {}
    return (
        f"Backtest {data.get('status')} para {data.get('strategy_name')} "
        f"en {data.get('dataset_id')}. Retorno: {metrics.get('total_return_pct', 0)}%, "
        f"trades: {metrics.get('trades_count', 0)}."
    )


def export_json(result: Any) -> str:
    data = _public_result(result)
    data["executive_summary"] = executive_summary(result)
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def export_csv(result: Any) -> str:
    data = _public_result(result)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "key", "value"])
    writer.writerow(["summary", "executive_summary", executive_summary(result)])
    for key, value in data.get("parameters", {}).items():
        writer.writerow(["parameters", key, value])
    for key, value in (data.get("metrics") or {}).items():
        if key != "equity_curve":
            writer.writerow(["metrics", key, value])
    for trade in data.get("trades", []):
        writer.writerow(["trade", "item", json.dumps(trade, sort_keys=True)])
    for point in (data.get("metrics") or {}).get("equity_curve", []):
        writer.writerow(["equity_curve", "point", json.dumps(point, sort_keys=True)])
    return output.getvalue()


def export_markdown(result: Any) -> str:
    data = _public_result(result)
    metrics = data.get("metrics") or {}
    lines = [
        "# Backtest Report",
        "",
        f"## Executive Summary\n\n{executive_summary(result)}",
        "",
        "## Parameters",
    ]
    for key, value in data.get("parameters", {}).items():
        lines.append(f"- **{key}**: {value}")
    lines.extend(["", "## Metrics"])
    for key, value in metrics.items():
        if key != "equity_curve":
            lines.append(f"- **{key}**: {value}")
    lines.extend(
        [
            "",
            "## Trades",
            f"Total trades: {len(data.get('trades', []))}",
            "",
            "## Equity Curve",
            f"Points: {len(metrics.get('equity_curve', []))}",
        ]
    )
    return "\n".join(lines)
