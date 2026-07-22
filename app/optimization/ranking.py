from __future__ import annotations

from decimal import Decimal
from typing import Literal

from app.optimization.results import OptimizationResult

RankingMetric = Literal["return", "sharpe", "profit_factor", "drawdown", "composite"]


class RankingEngine:
    def rank(
        self,
        results: list[OptimizationResult],
        *,
        by: RankingMetric = "composite",
        reverse: bool = True,
    ) -> list[OptimizationResult]:
        def key(result: OptimizationResult) -> Decimal:
            if by == "return":
                return result.total_return_pct
            if by == "sharpe":
                return result.sharpe
            if by == "profit_factor":
                return result.profit_factor or Decimal("0")
            if by == "drawdown":
                return -result.max_drawdown_pct
            return result.composite_score

        return sorted(results, key=key, reverse=reverse)

    def top(
        self,
        results: list[OptimizationResult],
        n: int = 10,
        *,
        by: RankingMetric = "composite",
    ) -> list[OptimizationResult]:
        return self.rank(results, by=by)[:n]

    def bottom(
        self,
        results: list[OptimizationResult],
        n: int = 10,
        *,
        by: RankingMetric = "composite",
    ) -> list[OptimizationResult]:
        return self.rank(results, by=by, reverse=False)[:n]
