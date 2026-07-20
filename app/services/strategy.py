from dataclasses import dataclass
from typing import Literal

Action = Literal["buy", "sell", "hold"]

@dataclass(frozen=True)
class Signal:
    action: Action
    confidence: int
    reason: str
    reference_price: float

def momentum_signal(last: float, high: float, low: float, volume: float) -> Signal:
    if last <= 0 or high <= low:
        return Signal("hold", 0, "Datos insuficientes o inválidos.", last)

    position = (last - low) / (high - low)
    range_pct = ((high - low) / last) * 100 if last else 0

    if position >= 0.82 and volume > 0 and range_pct >= 1:
        return Signal(
            "buy",
            min(75, int(55 + position * 20)),
            "Momentum positivo: precio cerca del máximo de 24 h. Requiere confirmación y control de riesgo.",
            last,
        )
    if position <= 0.18 and volume > 0 and range_pct >= 1:
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
