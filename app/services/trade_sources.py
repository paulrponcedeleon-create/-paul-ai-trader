from __future__ import annotations

from typing import Any

MANUAL_SOURCE = "manual"
RUNTIME_SOURCE = "runtime"
EXPLORATION_SOURCE = "exploration"
UNKNOWN_SOURCE = "unknown"

POSITION_SOURCES = (MANUAL_SOURCE, RUNTIME_SOURCE, EXPLORATION_SOURCE)
BOT_SOURCES = frozenset({RUNTIME_SOURCE, EXPLORATION_SOURCE})
LEARNING_SOURCES = frozenset(POSITION_SOURCES)

_SOURCE_LABELS = {
    MANUAL_SOURCE: "Manual · Paul",
    RUNTIME_SOURCE: "Bot · estrategia",
    EXPLORATION_SOURCE: "IA exploratoria",
    UNKNOWN_SOURCE: "Origen histórico",
}


def normalize_position_source(value: Any) -> str:
    source = str(value or "").strip().lower()
    return source if source in LEARNING_SOURCES else UNKNOWN_SOURCE


def infer_position_source(item: dict[str, Any]) -> str:
    explicit = normalize_position_source(item.get("source"))
    if explicit != UNKNOWN_SOURCE:
        return explicit

    risk_check = str(item.get("risk_check") or "").strip().lower()
    if risk_check.startswith("paper_exploration_"):
        return EXPLORATION_SOURCE
    if risk_check in {"strategy_buy", "strategy_sell"} or risk_check.startswith(
        "runtime_"
    ):
        return RUNTIME_SOURCE
    if item.get("correlation_id") and "strategy" in risk_check:
        return RUNTIME_SOURCE
    return MANUAL_SOURCE


def source_group(source: Any) -> str:
    normalized = normalize_position_source(source)
    if normalized == MANUAL_SOURCE:
        return "manual"
    if normalized in BOT_SOURCES:
        return "bot"
    return "unknown"


def source_label(source: Any) -> str:
    return _SOURCE_LABELS[normalize_position_source(source)]


def public_source(source: Any) -> dict[str, Any]:
    normalized = normalize_position_source(source)
    return {
        "source": normalized,
        "source_group": source_group(normalized),
        "source_label": source_label(normalized),
        "learning_eligible": normalized in LEARNING_SOURCES,
    }
