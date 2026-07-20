from dataclasses import dataclass
from app.config import settings

@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str

def validate_order(
    book: str,
    side: str,
    amount_mxn: float,
    daily_pnl_mxn: float,
    open_orders: int,
) -> RiskDecision:
    book = book.lower()
    if book not in settings.allowed_books_set:
        return RiskDecision(False, f"Mercado no autorizado: {book}")
    if side not in {"buy", "sell"}:
        return RiskDecision(False, "Tipo de orden inválido.")
    if amount_mxn <= 0:
        return RiskDecision(False, "El monto debe ser mayor que cero.")
    if amount_mxn > settings.max_order_mxn:
        return RiskDecision(False, f"Excede el máximo por operación: ${settings.max_order_mxn:,.2f} MXN.")
    if daily_pnl_mxn <= -abs(settings.max_daily_loss_mxn):
        return RiskDecision(False, "Bloqueado por límite diario de pérdida.")
    if open_orders >= settings.max_open_orders:
        return RiskDecision(False, "Alcanzaste el máximo de órdenes abiertas.")
    return RiskDecision(True, "Orden dentro de los límites configurados.")
