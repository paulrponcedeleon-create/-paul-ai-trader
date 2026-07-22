from __future__ import annotations

import json
from typing import Any


def export_market_data_status_json(status: dict[str, Any]) -> str:
    return json.dumps(status, ensure_ascii=False, sort_keys=True, indent=2)


def export_market_data_status_markdown(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Live Market Data Status",
            "",
            f"- Provider: {status.get('provider')}",
            f"- Connected: {status.get('connected')}",
            f"- Read only: {status.get('read_only')}",
            f"- Uptime seconds: {status.get('uptime_seconds')}",
            f"- Reconnects: {status.get('reconnects')}",
            f"- Last heartbeat: {status.get('last_heartbeat_at')}",
            f"- Last error: {status.get('last_error')}",
        ]
    )


def market_data_quality_report(
    *,
    status: dict[str, Any],
    latency_ms: float | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "connection": status,
        "uptime_seconds": status.get("uptime_seconds", 0),
        "reconnects": status.get("reconnects", 0),
        "latency_ms": latency_ms,
        "quality": "limited" if status.get("last_error") else "ok",
        "events": events or [],
    }
