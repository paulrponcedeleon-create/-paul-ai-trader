from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.services.backtest_metrics import to_decimal


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str = "ok"


@dataclass(frozen=True)
class RiskLimits:
    max_risk_per_trade_pct: Decimal | int | float | str = Decimal("2")
    max_daily_risk_pct: Decimal | int | float | str = Decimal("5")
    max_daily_loss_mxn: Decimal | int | float | str = Decimal("1000")
    max_positions: int = 3
    max_asset_exposure_pct: Decimal | int | float | str = Decimal("50")
    max_total_exposure_pct: Decimal | int | float | str = Decimal("80")


class RiskManager:
    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def evaluate_open(
        self,
        *,
        book: str,
        amount_mxn: Decimal,
        equity_mxn: Decimal,
        daily_realized_pnl_mxn: Decimal,
        open_positions_count: int,
        asset_exposure_mxn: Decimal,
        total_exposure_mxn: Decimal,
    ) -> RiskDecision:
        if open_positions_count >= self.limits.max_positions:
            return RiskDecision(False, "Límite de posiciones abiertas excedido.")
        if daily_realized_pnl_mxn <= -to_decimal(self.limits.max_daily_loss_mxn):
            return RiskDecision(False, "Pérdida máxima diaria excedida.")
        if equity_mxn <= 0:
            return RiskDecision(False, "Equity inválida.")
        risk_pct = (amount_mxn / equity_mxn) * Decimal("100")
        if risk_pct > to_decimal(self.limits.max_risk_per_trade_pct):
            return RiskDecision(False, "Riesgo máximo por operación excedido.")
        asset_pct = ((asset_exposure_mxn + amount_mxn) / equity_mxn) * Decimal("100")
        if asset_pct > to_decimal(self.limits.max_asset_exposure_pct):
            return RiskDecision(False, f"Exposición máxima para {book} excedida.")
        total_pct = ((total_exposure_mxn + amount_mxn) / equity_mxn) * Decimal("100")
        if total_pct > to_decimal(self.limits.max_total_exposure_pct):
            return RiskDecision(False, "Exposición total máxima excedida.")
        return RiskDecision(True)
