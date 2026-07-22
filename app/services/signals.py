from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.indicators import price_position, range_pct

Action = Literal["buy", "sell", "hold"]


@dataclass(frozen=True)
class Signal:
    action: Action
    confidence: int
    reason: str
    reference_price: float


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
