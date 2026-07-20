from dataclasses import dataclass
from .config import settings

@dataclass
class RiskDecision:
    allowed: bool
    reason: str

def validate_order(book: str, side: str, amount_mxn: float, daily_pnl_mxn: float,
                   open_orders: int, approved: bool) -> RiskDecision:
    if book.lower() not in settings.allowed_books_set:
        return RiskDecision(False, f"Mercado no autorizado: {book}")
    if side not in {"buy", "sell"}:
        return RiskDecision(False, "Tipo de operación inválido.")
    if amount_mxn <= 0:
        return RiskDecision(False, "El monto debe ser mayor a cero.")
    if amount_mxn > settings.max_order_mxn:
        return RiskDecision(False, f"Excede el máximo por orden: ${settings.max_order_mxn:,.2f} MXN")
    if daily_pnl_mxn <= -abs(settings.max_daily_loss_mxn):
        return RiskDecision(False, "Bloqueado por pérdida diaria máxima.")
    if open_orders >= settings.max_open_orders:
        return RiskDecision(False, "Ya alcanzaste el máximo de órdenes abiertas.")
    if settings.require_manual_approval and not approved:
        return RiskDecision(False, "Falta aprobación manual.")
    return RiskDecision(True, "Orden dentro de los límites de seguridad.")
