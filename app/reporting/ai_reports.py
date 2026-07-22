from __future__ import annotations

import json
from typing import Any


def _public(decision: Any) -> dict[str, Any]:
    return (
        decision.to_public_dict()
        if hasattr(decision, "to_public_dict")
        else dict(decision)
    )


def export_decision_report(decision: Any) -> str:
    return json.dumps(_public(decision), ensure_ascii=False, sort_keys=True, indent=2)


def export_confidence_report(decision: Any) -> str:
    data = _public(decision)
    return json.dumps(
        {
            "confidence": data["confidence"],
            "score": data["score"],
            "risk_factors": data["explanation"]["risk_factors"],
        },
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )


def export_market_regime_report(decision: Any) -> str:
    data = _public(decision)
    return json.dumps(
        {
            "market_regime": data["market_regime"],
            "primary_reason": data["explanation"]["primary_reason"],
        },
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
