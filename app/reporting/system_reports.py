from __future__ import annotations

import csv
from html import escape
import io
import json
from typing import Any


def export_system_health_report(data: dict[str, Any]) -> dict[str, Any]:
    return {"report": "system_health", "data": data}


def export_system_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def export_system_csv(data: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "value"])
    for key, value in data.items():
        writer.writerow([key, json.dumps(value, sort_keys=True, default=str)])
    return output.getvalue()


def export_system_markdown(data: dict[str, Any]) -> str:
    return "\n".join(
        ["# System Report", ""] + [f"- **{k}**: {v}" for k, v in data.items()]
    )


def export_system_html(data: dict[str, Any]) -> str:
    rows = "".join(
        f"<tr><th>{escape(str(k))}</th><td>{escape(str(v))}</td></tr>"
        for k, v in data.items()
    )
    return f"<!doctype html><html><body><h1>System Report</h1><table>{rows}</table></body></html>"
