from __future__ import annotations

import csv
from html import escape
import io
import json
from typing import Any

from app.burnin import BurnInReport


def _data(report: BurnInReport | dict[str, Any]) -> dict[str, Any]:
    return report.to_public_dict() if isinstance(report, BurnInReport) else report


def export_burnin_json(report: BurnInReport | dict[str, Any]) -> str:
    return json.dumps(_data(report), ensure_ascii=False, sort_keys=True, indent=2)


def export_burnin_csv(report: BurnInReport | dict[str, Any]) -> str:
    data = _data(report)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "value"])
    for key, value in data.items():
        if key != "cycle_metrics":
            writer.writerow([key, json.dumps(value, default=str, sort_keys=True)])
    writer.writerow([])
    writer.writerow(["cycle", "runtime_ms", "memory_bytes", "cpu_seconds", "errors"])
    for item in data.get("cycle_metrics", []):
        writer.writerow(
            [
                item.get("cycle"),
                item.get("runtime_ms"),
                item.get("memory_bytes"),
                item.get("cpu_seconds"),
                item.get("errors"),
            ]
        )
    return output.getvalue()


def export_burnin_markdown(report: BurnInReport | dict[str, Any]) -> str:
    data = _data(report)
    return "\n".join(
        [
            "# Burn-In Report",
            "",
            f"- Cycles: {data.get('cycles_executed', 0)}",
            f"- Average cycle ms: {data.get('average_cycle_ms', 0)}",
            f"- Min cycle ms: {data.get('min_cycle_ms', 0)}",
            f"- Max cycle ms: {data.get('max_cycle_ms', 0)}",
            f"- Errors: {data.get('errors', 0)}",
            f"- Reconnects: {data.get('reconnects', 0)}",
            f"- Memory growth bytes: {data.get('memory_growth_bytes', 0)}",
            f"- Alerts: {', '.join(data.get('alerts', [])) or 'none'}",
        ]
    )


def export_burnin_html(report: BurnInReport | dict[str, Any]) -> str:
    data = _data(report)
    rows = "".join(
        f"<tr><th>{escape(str(key))}</th><td>{escape(str(value))}</td></tr>"
        for key, value in data.items()
        if key != "cycle_metrics"
    )
    return (
        "<!doctype html><html><body><h1>Burn-In Report</h1>"
        f"<table>{rows}</table></body></html>"
    )
