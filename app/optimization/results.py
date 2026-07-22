from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class OptimizationResult:
    parameters: dict[str, Any]
    strategy_name: str
    strategy_version: str
    total_return_pct: Decimal
    max_drawdown_pct: Decimal
    sharpe: Decimal
    profit_factor: Decimal | None
    win_rate_pct: Decimal
    trades_count: int
    composite_score: Decimal
    backtest_status: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "parameters": self.parameters,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "total_return_pct": float(self.total_return_pct),
            "max_drawdown_pct": float(self.max_drawdown_pct),
            "sharpe": float(self.sharpe),
            "profit_factor": float(self.profit_factor)
            if self.profit_factor is not None
            else None,
            "win_rate_pct": float(self.win_rate_pct),
            "trades_count": self.trades_count,
            "composite_score": float(self.composite_score),
            "backtest_status": self.backtest_status,
        }
