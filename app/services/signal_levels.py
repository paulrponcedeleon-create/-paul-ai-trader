from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SignalLevel:
    level: str
    color: str
    label: str
    score: float
    confidence: float
    explanation: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "color": self.color,
            "label": self.label,
            "score": round(self.score, 2),
            "confidence": round(self.confidence, 2),
            "level_explanation": self.explanation,
        }


def _normalize_percent(value: Any) -> float:
    try:
        normalized = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if 0 < normalized <= 1:
        normalized *= 100
    return max(0.0, min(100.0, normalized))


def score_for_action(action: str | None, confidence: Any) -> float:
    """Convert a basic BUY/HOLD/SELL signal into the shared 0-100 scale."""

    normalized_action = str(action or "hold").strip().lower()
    normalized_confidence = _normalize_percent(confidence)
    if normalized_action == "buy":
        return max(50.0, normalized_confidence)
    if normalized_action == "sell":
        return min(25.0, 100.0 - normalized_confidence)
    return 50.0


def classify_signal_level(
    *,
    score: Any,
    confidence: Any,
    action: str | None = None,
    critical_penalty: bool = False,
) -> SignalLevel:
    """Return the single five-level interpretation used by Runtime and UI.

    The color is descriptive only. It never authorizes an order or bypasses
    Risk Engine and LIVE_TRADING=false.
    """

    normalized_score = _normalize_percent(score)
    normalized_confidence = _normalize_percent(confidence)
    normalized_action = str(action or "hold").strip().lower()

    if critical_penalty:
        return SignalLevel(
            "critical",
            "red",
            "Riesgo alto / salida",
            normalized_score,
            normalized_confidence,
            "Existe una penalización crítica; no se considera una oportunidad operable.",
        )

    effective_score = min(normalized_score, normalized_confidence + 15.0)

    if normalized_action == "sell" or effective_score < 30 or normalized_confidence < 25:
        return SignalLevel(
            "critical",
            "red",
            "Riesgo alto / salida",
            normalized_score,
            normalized_confidence,
            "La señal favorece salida, el score es muy bajo o la confianza es insuficiente.",
        )
    if effective_score < 45 or normalized_confidence < 40:
        return SignalLevel(
            "unfavorable",
            "orange",
            "Desfavorable",
            normalized_score,
            normalized_confidence,
            "La relación entre score y confianza todavía es desfavorable.",
        )
    if effective_score < 65 or normalized_confidence < 60:
        return SignalLevel(
            "observe",
            "yellow",
            "Mantener y observar",
            normalized_score,
            normalized_confidence,
            "No existe evidencia suficiente para una entrada fuerte; conviene observar.",
        )
    if effective_score < 85 or normalized_confidence < 80:
        return SignalLevel(
            "favorable",
            "green",
            "Favorable",
            normalized_score,
            normalized_confidence,
            "Score y confianza son favorables, sujetos a las reglas de riesgo.",
        )
    return SignalLevel(
        "exceptional",
        "blue",
        "Oportunidad excepcional",
        normalized_score,
        normalized_confidence,
        "Score y confianza son excepcionalmente altos, sin omitir controles de riesgo.",
    )
