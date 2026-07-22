from __future__ import annotations

import json
from typing import Any


def export_broker_status_json(health: Any) -> str:
    data = (
        health.to_public_dict() if hasattr(health, "to_public_dict") else dict(health)
    )
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def export_broker_status_markdown(health: Any) -> str:
    data = (
        health.to_public_dict() if hasattr(health, "to_public_dict") else dict(health)
    )
    return "\n".join(
        [
            "# Broker Status",
            "",
            f"- Connected: {data.get('connected')}",
            f"- Mode: {data.get('mode')}",
            f"- Live enabled: {data.get('live_enabled')}",
            f"- Status: {data.get('status')}",
            f"- Errors: {', '.join(data.get('errors', []))}",
        ]
    )
