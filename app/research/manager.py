from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from itertools import product
import math
import random
from statistics import mean, pstdev
from typing import Any
from uuid import uuid4

from app.experiments import Experiment, ExperimentManager, ExperimentResult


@dataclass(frozen=True)
class MonteCarloResult:
    iterations: int
    seed: int
    returns: tuple[float, ...]
    expected_return: float
    expected_drawdown: float
    worst_case: float
    best_case: float
    percentile_5: float
    percentile_50: float
    percentile_95: float
    probability_of_loss: float

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "iterations": self.iterations,
            "seed": self.seed,
            "returns": list(self.returns),
            "expected_return": _finite(self.expected_return),
            "expected_drawdown": _finite(self.expected_drawdown),
            "worst_case": _finite(self.worst_case),
            "best_case": _finite(self.best_case),
            "percentile_5": _finite(self.percentile_5),
            "percentile_50": _finite(self.percentile_50),
            "percentile_95": _finite(self.percentile_95),
            "probability_of_loss": _finite(self.probability_of_loss),
        }


@dataclass(frozen=True)
class ResearchPortfolio:
    strategy_weights: dict[str, float]
    correlation_matrix: dict[str, dict[str, float]]
    expected_return: float
    expected_risk: float
    combined_sharpe: float
    diversification_score: float

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "strategy_weights": self.strategy_weights,
            "correlation_matrix": self.correlation_matrix,
            "expected_return": _finite(self.expected_return),
            "expected_risk": _finite(self.expected_risk),
            "combined_sharpe": _finite(self.combined_sharpe),
            "diversification_score": _finite(self.diversification_score),
        }


@dataclass(frozen=True)
class ResearchResult:
    experiment_result: ExperimentResult
    robustness: dict[str, float]
    monte_carlo: MonteCarloResult
    rank_score: float

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "experiment_result": self.experiment_result.to_public_dict(),
            "robustness": {
                key: _finite(value) for key, value in self.robustness.items()
            },
            "monte_carlo": self.monte_carlo.to_public_dict(),
            "rank_score": _finite(self.rank_score),
        }


@dataclass(frozen=True)
class ResearchRun:
    id: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    results: tuple[ResearchResult, ...]
    portfolio: ResearchPortfolio
    recommendations: tuple[str, ...]

    def to_public_dict(self) -> dict[str, Any]:
        ranking = sorted(self.results, key=lambda item: item.rank_score, reverse=True)
        return {
            "id": self.id,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "results": [result.to_public_dict() for result in self.results],
            "ranking": [result.to_public_dict() for result in ranking],
            "portfolio": self.portfolio.to_public_dict(),
            "recommendations": list(self.recommendations),
        }


class ResearchManager:
    def __init__(self, experiment_manager: ExperimentManager) -> None:
        self.experiment_manager = experiment_manager
        self.current_run: ResearchRun | None = None
        self.history: dict[str, ResearchRun] = {}

    def start(self, spec: dict[str, Any]) -> ResearchRun:
        started = _utc_now()
        try:
            experiments = self._build_experiments(spec)
            mode = spec.get("mode", "backtest")
            raw_results = [
                self.experiment_manager.run(experiment.id, mode).result
                for experiment in experiments
            ]
            research_results = tuple(
                self._research_result(
                    result,
                    raw_results,
                    seed=int(spec.get("monte_carlo_seed", 7)),
                    iterations=int(spec.get("monte_carlo_iterations", 100)),
                )
                for result in raw_results
            )
            portfolio = self._build_portfolio(research_results)
            recommendations = _recommend(research_results)
            run = ResearchRun(
                str(uuid4()),
                "completed",
                started,
                _utc_now(),
                research_results,
                portfolio,
                recommendations,
            )
        except Exception as exc:
            run = ResearchRun(
                str(uuid4()),
                "failed",
                started,
                _utc_now(),
                tuple(),
                _empty_portfolio(),
                (f"research_failed:{type(exc).__name__}",),
            )
        self.current_run = run
        self.history[run.id] = run
        return run

    def status(self) -> dict[str, Any]:
        return {
            "running": False,
            "current_run_id": self.current_run.id if self.current_run else None,
            "status": self.current_run.status if self.current_run else "idle",
            "runs": len(self.history),
        }

    def results(self) -> dict[str, Any]:
        if self.current_run is None:
            return {"results": [], "ranking": []}
        return self.current_run.to_public_dict()

    def _build_experiments(self, spec: dict[str, Any]) -> list[Experiment]:
        explicit = spec.get("experiments") or []
        if explicit:
            experiments = [_experiment_from_spec(item) for item in explicit]
        else:
            experiments = _expand_experiments(spec)
        for experiment in experiments:
            if self.experiment_manager.get(experiment.id) is None:
                self.experiment_manager.create(experiment)
        return experiments

    def _research_result(
        self,
        result: ExperimentResult,
        all_results: list[ExperimentResult],
        *,
        seed: int,
        iterations: int,
    ) -> ResearchResult:
        similar_returns = [
            item.metrics.get("return", 0.0)
            for item in all_results
            if item.experiment_id == result.experiment_id
            or item.metrics.get("trades", 0.0) == result.metrics.get("trades", 0.0)
        ] or [result.metrics.get("return", 0.0)]
        monte_carlo = monte_carlo_simulation(
            similar_returns, seed=seed, iterations=iterations
        )
        robustness = robustness_metrics(result, all_results)
        score = _rank_score(result.metrics, robustness, monte_carlo)
        return ResearchResult(result, robustness, monte_carlo, score)

    def _build_portfolio(
        self, results: tuple[ResearchResult, ...]
    ) -> ResearchPortfolio:
        if not results:
            return _empty_portfolio()
        by_strategy: dict[str, list[float]] = {}
        for result in results:
            data = result.experiment_result.payload
            strategy = str(data.get("strategy_name") or data.get("strategy", "unknown"))
            if "strategy_name" not in data and "experiment" in data:
                strategy = str(data["experiment"].get("strategy_name", strategy))
            by_strategy.setdefault(strategy, []).append(
                result.experiment_result.metrics.get("return", 0.0)
            )
        matrix = correlation_matrix(by_strategy)
        weights = {name: 1 / len(by_strategy) for name in sorted(by_strategy)}
        returns = [mean(values) for values in by_strategy.values()]
        expected_return = sum(returns) / len(returns) if returns else 0.0
        expected_risk = pstdev(returns) if len(returns) > 1 else 0.0
        avg_corr = _average_off_diagonal(matrix)
        diversification = max(0.0, 1.0 - avg_corr)
        sharpe = expected_return / expected_risk if expected_risk > 0 else 0.0
        return ResearchPortfolio(
            weights, matrix, expected_return, expected_risk, sharpe, diversification
        )


def monte_carlo_simulation(
    historical_returns: list[float], *, seed: int = 7, iterations: int = 100
) -> MonteCarloResult:
    clean = [
        float(value) for value in historical_returns if math.isfinite(float(value))
    ]
    if not clean:
        clean = [0.0]
    rng = random.Random(seed)
    simulated: list[float] = []
    drawdowns: list[float] = []
    for _ in range(max(iterations, 1)):
        path = [rng.choice(clean) for _ in range(len(clean))]
        total_return = sum(path)
        simulated.append(total_return)
        drawdowns.append(_path_drawdown(path))
    ordered = sorted(simulated)
    losses = [value for value in simulated if value < 0]
    return MonteCarloResult(
        len(simulated),
        seed,
        tuple(round(value, 6) for value in simulated),
        mean(simulated),
        mean(drawdowns),
        min(simulated),
        max(simulated),
        _percentile(ordered, 5),
        _percentile(ordered, 50),
        _percentile(ordered, 95),
        len(losses) / len(simulated),
    )


def correlation_matrix(series: dict[str, list[float]]) -> dict[str, dict[str, float]]:
    names = sorted(series)
    return {
        left: {right: _correlation(series[left], series[right]) for right in names}
        for left in names
    }


def robustness_metrics(
    result: ExperimentResult, all_results: list[ExperimentResult]
) -> dict[str, float]:
    returns = [item.metrics.get("return", 0.0) for item in all_results]
    own_return = result.metrics.get("return", 0.0)
    best = max(returns) if returns else own_return
    avg = mean(returns) if returns else own_return
    first_half = returns[: max(1, len(returns) // 2)]
    second_half = returns[max(1, len(returns) // 2) :] or first_half
    sensitivity = pstdev(returns) if len(returns) > 1 else 0.0
    consistency = (
        len([value for value in returns if value >= 0]) / len(returns)
        if returns
        else 0.0
    )
    temporal_degradation = mean(first_half) - mean(second_half)
    overfitting = abs(best - avg)
    stability = result.metrics.get("stability_score", 0.0)
    robustness = max(
        0.0,
        stability
        + consistency * 10
        - sensitivity
        - overfitting
        - max(temporal_degradation, 0.0),
    )
    return {
        "parameter_sensitivity": sensitivity,
        "stability": stability,
        "overfitting": overfitting,
        "temporal_degradation": temporal_degradation,
        "consistency": consistency,
        "robustness": robustness,
    }


def _expand_experiments(spec: dict[str, Any]) -> list[Experiment]:
    strategies = spec.get("strategies") or [spec.get("strategy_name", "momentum")]
    assets = spec.get("assets") or ["btc_mxn"]
    timeframes = spec.get("timeframes") or ["1m"]
    capitals = spec.get("capitals") or [spec.get("initial_capital_mxn", 10000)]
    risk_configs = spec.get("risk_configs") or [spec.get("risk_config", {})]
    parameter_sets = spec.get("parameter_sets") or [spec.get("parameters", {})]
    experiments: list[Experiment] = []
    for strategy, asset, timeframe, capital, risk_config, parameters in product(
        strategies, assets, timeframes, capitals, risk_configs, parameter_sets
    ):
        experiments.append(
            Experiment(
                name=f"research-{strategy}-{asset}-{timeframe}-{len(experiments) + 1}",
                description="Generated by ResearchManager.",
                strategy_name=str(strategy),
                parameters=dict(parameters),
                assets=(str(asset),),
                timeframe=str(timeframe),
                initial_capital_mxn=Decimal(str(capital)),
                trade_amount_mxn=Decimal(str(spec.get("trade_amount_mxn", 1000))),
                fee_rate=Decimal(str(spec.get("fee_rate", 0.001))),
                risk_config=dict(risk_config),
                dataset_id=spec.get("dataset_id") or f"{asset}/{timeframe}/default.csv",
                parameter_space={
                    key: tuple(value)
                    for key, value in (spec.get("parameter_space") or {}).items()
                },
            )
        )
    return experiments


def _experiment_from_spec(spec: dict[str, Any]) -> Experiment:
    return Experiment(
        name=str(spec.get("name", "research-experiment")),
        description=str(spec.get("description", "Generated research experiment.")),
        strategy_name=str(spec.get("strategy_name", "momentum")),
        strategy_version=str(spec.get("strategy_version", "1.0")),
        parameters=dict(spec.get("parameters", {})),
        assets=tuple(spec.get("assets", ["btc_mxn"])),
        timeframe=str(spec.get("timeframe", "1m")),
        initial_capital_mxn=Decimal(str(spec.get("initial_capital_mxn", 10000))),
        trade_amount_mxn=Decimal(str(spec.get("trade_amount_mxn", 1000))),
        fee_rate=Decimal(str(spec.get("fee_rate", 0.001))),
        risk_config=dict(spec.get("risk_config", {})),
        dataset_id=spec.get("dataset_id"),
        parameter_space={
            key: tuple(value)
            for key, value in (spec.get("parameter_space") or {}).items()
        },
    )


def _rank_score(
    metrics: dict[str, float],
    robustness: dict[str, float],
    monte_carlo: MonteCarloResult,
) -> float:
    return (
        metrics.get("profit_factor", 0.0)
        + metrics.get("sharpe", 0.0) * 10
        + metrics.get("stability_score", 0.0)
        + robustness.get("robustness", 0.0)
        + monte_carlo.expected_return
        + robustness.get("consistency", 0.0) * 10
        - metrics.get("drawdown", 0.0)
        - monte_carlo.probability_of_loss * 10
        - abs(monte_carlo.expected_drawdown)
    )


def _recommend(results: tuple[ResearchResult, ...]) -> tuple[str, ...]:
    if not results:
        return ("No hay resultados suficientes para recomendar estrategias.",)
    ranked = sorted(results, key=lambda item: item.rank_score, reverse=True)
    best = ranked[0]
    worst = ranked[-1]
    return (
        f"Priorizar experimento {best.experiment_result.experiment_id} por score {best.rank_score:.4f}.",
        f"Revisar experimento {worst.experiment_result.experiment_id} antes de asignar capital.",
    )


def _empty_portfolio() -> ResearchPortfolio:
    return ResearchPortfolio({}, {}, 0.0, 0.0, 0.0, 0.0)


def _path_drawdown(path: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in path:
        equity += value
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
    return abs(max_drawdown)


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    index = (len(values) - 1) * percentile / 100
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return values[int(index)]
    weight = index - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def _correlation(left: list[float], right: list[float]) -> float:
    if left is right:
        return 1.0
    size = min(len(left), len(right))
    if size < 2:
        return 1.0 if left == right else 0.0
    x = left[:size]
    y = right[:size]
    mean_x = mean(x)
    mean_y = mean(y)
    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y, strict=True))
    denom_x = math.sqrt(sum((a - mean_x) ** 2 for a in x))
    denom_y = math.sqrt(sum((b - mean_y) ** 2 for b in y))
    denominator = denom_x * denom_y
    return numerator / denominator if denominator > 0 else 0.0


def _average_off_diagonal(matrix: dict[str, dict[str, float]]) -> float:
    values = [
        value
        for left, row in matrix.items()
        for right, value in row.items()
        if left != right
    ]
    return mean(values) if values else 0.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _finite(value: float) -> float:
    return value if math.isfinite(value) else 0.0
