from __future__ import annotations

import csv
from html import escape
import io
import json
from typing import Any


def _public(value: Any) -> Any:
    if hasattr(value, "to_public_dict"):
        return value.to_public_dict()
    if isinstance(value, list):
        return [_public(item) for item in value]
    if isinstance(value, dict):
        return {key: _public(item) for key, item in value.items()}
    return value


def export_analytics_json(report: dict[str, Any]) -> str:
    return json.dumps(_public(report), ensure_ascii=False, sort_keys=True, indent=2)


def export_analytics_csv(report: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "key", "value"])
    for section, value in _public(report).items():
        if isinstance(value, dict):
            for key, item in value.items():
                writer.writerow([section, key, item])
        else:
            writer.writerow([section, "value", json.dumps(value, sort_keys=True)])
    return output.getvalue()


def export_analytics_markdown(report: dict[str, Any]) -> str:
    data = _public(report)
    lines = ["# Analytics Report", "", "## Summary"]
    for key, value in (data.get("summary") or {}).items():
        lines.append(f"- **{key}**: {value}")
    lines.extend(
        [
            "",
            "## Equity",
            f"Points: {len(data.get('equity', []))}",
            "",
            "## Drawdown",
            f"Periods: {len(data.get('drawdown', []))}",
            "",
            "## Strategies",
            f"Items: {len(data.get('strategies', []))}",
            "",
            "## Assets",
            f"Items: {len(data.get('assets', []))}",
            "",
            "## AI Attribution",
            f"Items: {len(data.get('ai', []))}",
            "",
            "## Risk Attribution",
            str(data.get("risk", {})),
            "",
            "## Broker Analytics",
            str(data.get("broker", {})),
            "",
            "## Best Trades",
            str(data.get("best_trades", [])),
            "",
            "## Worst Trades",
            str(data.get("worst_trades", [])),
        ]
    )
    return "\n".join(lines)


def export_analytics_html(report: dict[str, Any]) -> str:
    data = _public(report)
    summary = data.get("summary") or {}
    rows = "".join(
        f"<tr><th>{escape(str(k))}</th><td>{escape(str(v))}</td></tr>"
        for k, v in summary.items()
    )
    return f"<!doctype html><html><head><meta charset='utf-8'><title>Analytics Report</title></head><body><h1>Analytics Report</h1><h2>Summary</h2><table>{rows}</table><h2>Equity</h2><p>{len(data.get('equity', []))} points</p><h2>Drawdown</h2><p>{len(data.get('drawdown', []))} periods</p><h2>Strategies</h2><pre>{escape(str(data.get('strategies', [])))}</pre><h2>Assets</h2><pre>{escape(str(data.get('assets', [])))}</pre><h2>AI Attribution</h2><pre>{escape(str(data.get('ai', [])))}</pre><h2>Risk Attribution</h2><pre>{escape(str(data.get('risk', {})))}</pre><h2>Broker Analytics</h2><pre>{escape(str(data.get('broker', {})))}</pre><h2>Best Trades</h2><pre>{escape(str(data.get('best_trades', [])))}</pre><h2>Worst Trades</h2><pre>{escape(str(data.get('worst_trades', [])))}</pre></body></html>"
