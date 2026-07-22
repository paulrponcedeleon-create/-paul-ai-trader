from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable

from app.optimization.parameter_space import ParameterSpace
from app.optimization.results import OptimizationResult
from app.services.backtesting import BacktestEngine, BacktestRequest, BacktestResult


@dataclass(frozen=True)
class OptimizationRequest:
    dataset_id: str
    strategy_name: str
    strategy_version: str = "1.0"
    initial_capital_mxn: Decimal | int | float | str = Decimal("10000")
    trade_amount_mxn: Decimal | int | float | str = Decimal("1000")
    fee_rate: Decimal | int | float | str = Decimal("0.001")
    parameter_space: ParameterSpace | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OptimizationReport:
    status: str
    strategy_name: str
    strategy_version: str
    dataset_id: str
    results: tuple[OptimizationResult, ...]
    error: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "dataset_id": self.dataset_id,
            "results": [result.to_public_dict() for result in self.results],
            "error": self.error,
        }


class OptimizationEngine:
    def __init__(
        self, *, backtest_engine: BacktestEngine, repository: Any | None = None
    ) -> None:
        self.backtest_engine = backtest_engine
        self.repository = repository

    def run(
        self, request: OptimizationRequest, combinations: Iterable[dict[str, Any]]
    ) -> OptimizationReport:
        run_id = None
        if self.repository is not None:
            created = self.repository.create_run(
                strategy_name=request.strategy_name,
                strategy_version=request.strategy_version,
                dataset_id=request.dataset_id,
                parameter_space=(
                    request.parameter_space.values if request.parameter_space else {}
                ),
                status="running",
            )
            run_id = int(created["id"])
        results: list[OptimizationResult] = []
        try:
            for parameters in combinations:
                merged = {**request.parameters, **parameters}
                backtest = self.backtest_engine.run(
                    BacktestRequest(
                        dataset_id=request.dataset_id,
                        strategy_name=request.strategy_name,
                        strategy_version=request.strategy_version,
                        initial_capital_mxn=request.initial_capital_mxn,
                        trade_amount_mxn=request.trade_amount_mxn,
                        fee_rate=request.fee_rate,
                        parameters=merged,
                    )
                )
                result = optimization_result_from_backtest(backtest, merged)
                results.append(result)
                if self.repository is not None and run_id is not None:
                    self.repository.add_result(run_id, result.to_public_dict())
            if self.repository is not None and run_id is not None:
                self.repository.update_run(
                    run_id, status="completed", results_count=len(results)
                )
            return OptimizationReport(
                "completed",
                request.strategy_name,
                request.strategy_version,
                request.dataset_id,
                tuple(results),
            )
        except Exception:
            if self.repository is not None and run_id is not None:
                self.repository.update_run(
                    run_id, status="failed", results_count=len(results)
                )
            return OptimizationReport(
                "failed",
                request.strategy_name,
                request.strategy_version,
                request.dataset_id,
                tuple(results),
                "No fue posible ejecutar la optimización.",
            )


def optimization_result_from_backtest(
    backtest: BacktestResult, parameters: dict[str, Any]
) -> OptimizationResult:
    metrics = backtest.metrics
    if metrics is None:
        zero = Decimal("0")
        return OptimizationResult(
            parameters,
            backtest.strategy_name,
            backtest.strategy_version,
            zero,
            zero,
            zero,
            zero,
            zero,
            0,
            zero,
            backtest.status,
        )
    sharpe = _sharpe(metrics.equity_curve)
    profit_factor = metrics.profit_factor
    composite = _composite(
        metrics.total_return_pct,
        metrics.max_drawdown_pct,
        sharpe,
        profit_factor,
        metrics.win_rate_pct,
    )
    return OptimizationResult(
        parameters=dict(parameters),
        strategy_name=backtest.strategy_name,
        strategy_version=backtest.strategy_version,
        total_return_pct=metrics.total_return_pct,
        max_drawdown_pct=metrics.max_drawdown_pct,
        sharpe=sharpe,
        profit_factor=profit_factor,
        win_rate_pct=metrics.win_rate_pct,
        trades_count=metrics.trades_count,
        composite_score=composite,
        backtest_status=backtest.status,
    )


def _sharpe(equity_curve: tuple[dict[str, Any], ...]) -> Decimal:
    if len(equity_curve) < 2:
        return Decimal("0")
    returns: list[Decimal] = []
    prev = Decimal(str(equity_curve[0]["equity_mxn"]))
    for point in equity_curve[1:]:
        current = Decimal(str(point["equity_mxn"]))
        if prev > 0:
            returns.append((current - prev) / prev)
        prev = current
    if not returns:
        return Decimal("0")
    mean = sum(returns, Decimal("0")) / Decimal(len(returns))
    variance = sum((value - mean) ** 2 for value in returns) / Decimal(len(returns))
    if variance == 0:
        return Decimal("0")
    return (mean / Decimal(str(variance.sqrt()))).quantize(Decimal("0.0001"))


def _composite(
    total_return: Decimal,
    drawdown: Decimal,
    sharpe: Decimal,
    profit_factor: Decimal | None,
    win_rate: Decimal,
) -> Decimal:
    pf = profit_factor or Decimal("0")
    return (
        total_return
        + (sharpe * Decimal("10"))
        + pf
        + (win_rate / Decimal("10"))
        - drawdown
    ).quantize(Decimal("0.0001"))
