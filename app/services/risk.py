from dataclasses import dataclass

from app.config import Settings, settings


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
    risk_settings: Settings | None = None,
) -> RiskDecision:
    current_settings = risk_settings or settings
    book = book.lower()
    if book not in current_settings.enabled_books_set:
        return RiskDecision(False, f"Mercado no autorizado: {book}")
    if side not in {"buy", "sell"}:
        return RiskDecision(False, "Tipo de orden inválido.")
    if not current_settings.live_trading and side == "sell":
        return RiskDecision(
            False,
            "En simulación spot no puedes vender un activo que no tienes. Usa Cerrar posición sobre una compra abierta.",
        )
    if amount_mxn <= 0:
        return RiskDecision(False, "El monto debe ser mayor que cero.")
    if amount_mxn > current_settings.max_order_mxn:
        return RiskDecision(
            False,
            f"Excede el máximo por operación: ${current_settings.max_order_mxn:,.2f} MXN.",
        )
    if daily_pnl_mxn <= -abs(current_settings.max_daily_loss_mxn):
        return RiskDecision(False, "Bloqueado por límite diario de pérdida.")
    if open_orders >= current_settings.max_open_orders:
        return RiskDecision(False, "Alcanzaste el máximo de órdenes abiertas.")
    return RiskDecision(True, "Orden dentro de los límites configurados.")
