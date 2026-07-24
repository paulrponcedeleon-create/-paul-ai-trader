from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.services.indicators import price_position, range_pct
from app.services.signal_levels import classify_signal_level, score_for_action

Action = Literal["buy", "sell", "hold"]


@dataclass(frozen=True)
class Signal:
    action: Action
    confidence: int
    reason: str
    reference_price: float
    score: float | None = None
    level: str = "critical"
    color: str = "red"
    label: str = "Riesgo alto / salida"
    level_explanation: str = ""

    def __post_init__(self) -> None:
        score = self.score
        if score is None:
            score = score_for_action(self.action, self.confidence)
        classification = classify_signal_level(
            score=score,
            confidence=self.confidence,
            action=self.action,
        )
        object.__setattr__(self, "score", classification.score)
        object.__setattr__(self, "level", classification.level)
        object.__setattr__(self, "color", classification.color)
        object.__setattr__(self, "label", classification.label)
        object.__setattr__(self, "level_explanation", classification.explanation)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "reason": self.reason,
            "reference_price": self.reference_price,
            "score": round(float(self.score or 0), 2),
            "level": self.level,
            "color": self.color,
            "label": self.label,
            "level_explanation": self.level_explanation,
        }


def momentum_signal(last: float, high: float, low: float, volume: float) -> Signal:
    position = price_position(last, high, low)
    if position is None:
        return Signal("hold", 0, "Datos insuficientes o inválidos.", last)

    current_range_pct = range_pct(last, high, low)

    if position >= 0.82 and volume > 0 and current_range_pct >= 1:
        return Signal(
            "buy",
            min(75, int(55 + position * 20)),
            "Momentum positivo: precio cerca del máximo de 24 h. Requiere confirmación y control de riesgo.",
            last,
        )
    if position <= 0.18 and volume > 0 and current_range_pct >= 1:
        return Signal(
            "sell",
            min(75, int(75 - position * 20)),
            "Señal defensiva: precio cerca del mínimo de 24 h. No implica venta automática.",
            last,
        )
    return Signal(
        "hold",
        50,
        "No existe suficiente ventaja estadística con la regla inicial.",
        last,
    )
