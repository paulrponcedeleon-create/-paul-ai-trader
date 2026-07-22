from __future__ import annotations

import json
from typing import Any

from app.live.models import ExecutionAuditRecord, GuardDecision


def export_live_status_report(status: dict[str, Any]) -> str:
    return json.dumps(status, ensure_ascii=False, sort_keys=True, indent=2)


def export_guard_report(decision: GuardDecision) -> dict[str, Any]:
    return decision.to_public_dict()


def export_audit_report(records: list[ExecutionAuditRecord]) -> dict[str, Any]:
    rows = [record.to_public_dict() for record in records]
    rejected = [row for row in rows if row["result"] == "rejected"]
    return {"items": rows, "total": len(rows), "rejections": len(rejected)}
