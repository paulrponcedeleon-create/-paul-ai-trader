from dataclasses import dataclass, asdict
from typing import Literal

Action = Literal["buy", "sell", "hold"]

@dataclass
class Signal:
    action: Action
    confidence: int
    score: int
    reason: str
    reference_price: float
    stop_pct: float
    target_pct: float

    def dict(self):
        return asdict(self)

def analyze_ticker(last: float, high: float, low: float, volume: float, bid: float, ask: float) -> Signal:
    if min(last, high, low) <= 0 or high <= low:
        return Signal("hold", 0, 0, "Datos insuficientes o inválidos.", last, 0, 0)

    position = (last - low) / (high - low)
    spread_pct = ((ask - bid) / last) * 100 if ask > bid > 0 else 99
    score = 0
    reasons = []

    if position >= 0.72:
        score += 2
        reasons.append("precio en la zona alta del rango de 24 h")
    elif position <= 0.28:
        score -= 2
        reasons.append("precio en la zona baja del rango de 24 h")

    if volume > 0:
        score += 1
        reasons.append("mercado con volumen reportado")

    if spread_pct <= 0.35:
        score += 1
        reasons.append("spread relativamente estrecho")
    elif spread_pct >= 1.0:
        score -= 1
        reasons.append("spread amplio")

    if score >= 3:
        return Signal("buy", min(80, 55 + score * 5), score, "; ".join(reasons), last, 1.5, 3.0)
    if score <= -2:
        return Signal("sell", min(75, 55 + abs(score) * 5), score, "; ".join(reasons), last, 1.2, 2.0)
    return Signal("hold", 50, score, "; ".join(reasons) or "Sin ventaja clara.", last, 0, 0)
