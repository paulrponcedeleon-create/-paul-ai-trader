from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import math
from typing import Any, Literal
from uuid import uuid4

from app.optimization.engine import OptimizationEngine, OptimizationRequest
from app.optimization.parameter_space import ParameterSpace
from app.optimization.search import GridSearchOptimizer
from app.paper_trading.engine import PaperTradingEngine
from app.paper_trading.models import PaperTradingRequest
from app.paper_trading.portfolio import PortfolioManager
from app.services.backtesting import BacktestEngine, BacktestRequest, BacktestResult
from app.services.historical_data import HistoricalDataProvider
from app.services.walk_forward import WalkForwardEngine, WalkForwardRequest

ExperimentMode = Literal["backtest", "walk_forward", "optimization", "paper_replay"]


@dataclass(frozen=True)
class Experiment:
    name: str
    description: str
    strategy_name: str
    parameters: dict[str, Any]
    assets: tuple[str, ...]
    timeframe: str
    initial_capital_mxn: Decimal
    start_at: datetime | None = None
    end_at: datetime | None = None
    risk_config: dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    strategy_version: str = "1.0"
    dataset_id: str | None = None
    trade_amount_mxn: Decimal = Decimal("1000")
    fee_rate: Decimal = Decimal("0.001")
    parameter_space: dict[str, tuple[Any, ...]] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "parameters": self.parameters,
            "assets": list(self.assets),
            "timeframe": self.timeframe,
            "initial_capital_mxn": float(self.initial_capital_mxn),
            "trade_amount_mxn": float(self.trade_amount_mxn),
            "fee_rate": float(self.fee_rate),
            "start_at": self.start_at.isoformat() if self.start_at else None,
            "end_at": self.end_at.isoformat() if self.end_at else None,
            "risk_config": self.risk_config,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "dataset_id": self.dataset_id,
            "parameter_space": {k: list(v) for k, v in self.parameter_space.items()},
        }


@dataclass(frozen=True)
class ExperimentResult:
    experiment_id: str
    mode: ExperimentMode
    status: str
    metrics: dict[str, float]
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "mode": self.mode,
            "status": self.status,
            "metrics": {key: _finite(value) for key, value in self.metrics.items()},
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class ExperimentRun:
    experiment: Experiment
    result: ExperimentResult

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "experiment": self.experiment.to_public_dict(),
            "result": self.result.to_public_dict(),
        }


@dataclass(frozen=True)
class ExperimentComparison:
    results: tuple[ExperimentResult, ...]
    ranking: tuple[dict[str, Any], ...]
    best_experiment_id: str | None
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "best_experiment_id": self.best_experiment_id,
            "ranking": list(self.ranking),
            "results": [result.to_public_dict() for result in self.results],
        }


class ExperimentRepository:
    def __init__(self) -> None:
        self.experiments: dict[str, Experiment] = {}
        self.results: dict[str, ExperimentResult] = {}

    def save_experiment(self, experiment: Experiment) -> Experiment:
        self.experiments[experiment.id] = experiment
        return experiment

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        return self.experiments.get(experiment_id)

    def list_experiments(self) -> list[Experiment]:
        return sorted(self.experiments.values(), key=lambda item: item.created_at)

    def save_result(self, result: ExperimentResult) -> ExperimentResult:
        self.results[result.id] = result
        return result

    def list_results(
        self, experiment_ids: tuple[str, ...] | None = None
    ) -> list[ExperimentResult]:
        values = list(self.results.values())
        if experiment_ids:
            selected = set(experiment_ids)
            values = [item for item in values if item.experiment_id in selected]
        return sorted(values, key=lambda item: item.created_at)


class ExperimentManager:
    def __init__(
        self,
        *,
        historical_data_provider: HistoricalDataProvider,
        repository: ExperimentRepository | None = None,
        backtest_engine: BacktestEngine | None = None,
    ) -> None:
        self.historical_data_provider = historical_data_provider
        self.repository = repository or ExperimentRepository()
        self.backtest_engine = backtest_engine or BacktestEngine(
            historical_data_provider=historical_data_provider
        )

    def create(self, experiment: Experiment) -> Experiment:
        self._validate_experiment(experiment)
        return self.repository.save_experiment(experiment)

    def list(self) -> list[Experiment]:
        return self.repository.list_experiments()

    def get(self, experiment_id: str) -> Experiment | None:
        return self.repository.get_experiment(experiment_id)

    def run(
        self, experiment_id: str, mode: ExperimentMode = "backtest"
    ) -> ExperimentRun:
        experiment = self._require_experiment(experiment_id)
        if mode == "walk_forward":
            result = self._run_walk_forward(experiment)
        elif mode == "optimization":
            result = self._run_optimization(experiment)
        elif mode == "paper_replay":
            result = self._run_paper_replay(experiment)
        else:
            result = self._run_backtest(experiment)
        self.repository.save_result(result)
        return ExperimentRun(experiment, result)

    def compare(
        self, experiment_ids: tuple[str, ...] | None = None
    ) -> ExperimentComparison:
        results = tuple(self.repository.list_results(experiment_ids))
        ranking = tuple(_rank(results))
        return ExperimentComparison(
            results=results,
            ranking=ranking,
            best_experiment_id=ranking[0]["experiment_id"] if ranking else None,
        )

    def _run_backtest(self, experiment: Experiment) -> ExperimentResult:
        backtest = self.backtest_engine.run(self._backtest_request(experiment))
        return ExperimentResult(
            experiment.id,
            "backtest",
            backtest.status,
            _metrics_from_backtest(backtest),
            backtest.to_public_dict(),
        )

    def _run_walk_forward(self, experiment: Experiment) -> ExperimentResult:
        if experiment.start_at is None or experiment.end_at is None:
            return ExperimentResult(
                experiment.id,
                "walk_forward",
                "failed",
                _zero_metrics(),
                {"error": "Walk-forward requiere start_at y end_at."},
            )
        report = WalkForwardEngine(self.backtest_engine).run(
            WalkForwardRequest(
                dataset_id=self._dataset_id(experiment),
                strategy_name=experiment.strategy_name,
                strategy_version=experiment.strategy_version,
                initial_capital_mxn=float(experiment.initial_capital_mxn),
                trade_amount_mxn=float(experiment.trade_amount_mxn),
                fee_rate=float(experiment.fee_rate),
                training_window_days=int(
                    experiment.risk_config.get("training_window_days", 30)
                ),
                validation_window_days=int(
                    experiment.risk_config.get("validation_window_days", 7)
                ),
                start_at=experiment.start_at,
                end_at=experiment.end_at,
                mode=experiment.risk_config.get("walk_forward_mode", "rolling"),
                parameters=experiment.parameters,
            )
        )
        metrics = _zero_metrics()
        metrics["return"] = float(report.consolidated.get("average_return_pct", 0.0))
        metrics["trades"] = float(report.consolidated.get("total_trades", 0.0))
        metrics["stability_score"] = _stability_score(metrics)
        return ExperimentResult(
            experiment.id,
            "walk_forward",
            "completed",
            metrics,
            {
                "mode": report.mode,
                "segments": len(report.segments),
                "consolidated": report.consolidated,
            },
        )

    def _run_optimization(self, experiment: Experiment) -> ExperimentResult:
        if not experiment.parameter_space:
            return ExperimentResult(
                experiment.id,
                "optimization",
                "failed",
                _zero_metrics(),
                {"error": "Optimization requiere parameter_space."},
            )
        parameter_space = ParameterSpace.from_dict(
            {key: list(values) for key, values in experiment.parameter_space.items()}
        )
        report = OptimizationEngine(backtest_engine=self.backtest_engine).run(
            OptimizationRequest(
                dataset_id=self._dataset_id(experiment),
                strategy_name=experiment.strategy_name,
                strategy_version=experiment.strategy_version,
                initial_capital_mxn=experiment.initial_capital_mxn,
                trade_amount_mxn=experiment.trade_amount_mxn,
                fee_rate=experiment.fee_rate,
                parameter_space=parameter_space,
                parameters=experiment.parameters,
            ),
            GridSearchOptimizer().generate(parameter_space),
        )
        public = report.to_public_dict()
        best = max(
            public["results"], key=lambda item: item["composite_score"], default=None
        )
        metrics = _metrics_from_optimization(best) if best else _zero_metrics()
        return ExperimentResult(
            experiment.id,
            "optimization",
            report.status,
            metrics,
            public,
        )

    def _run_paper_replay(self, experiment: Experiment) -> ExperimentResult:
        dataset = self.historical_data_provider.load_dataset(
            self._dataset_id(experiment)
        )
        portfolio = PortfolioManager(initial_cash_mxn=experiment.initial_capital_mxn)
        engine = PaperTradingEngine(portfolio=portfolio)
        engine.start(
            PaperTradingRequest(
                account_id=f"exp-{experiment.id}",
                book=dataset.book,
                strategy_name=experiment.strategy_name,
                strategy_version=experiment.strategy_version,
                parameters=experiment.parameters,
                fee_rate=experiment.fee_rate,
                sizing_method="fixed_size",
                sizing_value=experiment.trade_amount_mxn,
            )
        )
        snapshot = None
        for candle in dataset.candles:
            if experiment.start_at and candle.timestamp < experiment.start_at:
                continue
            if experiment.end_at and candle.timestamp > experiment.end_at:
                continue
            snapshot = engine.on_candle(candle)
        engine.stop()
        payload = (
            snapshot.to_public_dict()
            if snapshot
            else portfolio.snapshot({}).to_public_dict()
        )
        metrics = _metrics_from_paper(payload, float(experiment.initial_capital_mxn))
        return ExperimentResult(
            experiment.id, "paper_replay", "completed", metrics, payload
        )

    def _backtest_request(self, experiment: Experiment) -> BacktestRequest:
        return BacktestRequest(
            dataset_id=self._dataset_id(experiment),
            strategy_name=experiment.strategy_name,
            strategy_version=experiment.strategy_version,
            initial_capital_mxn=experiment.initial_capital_mxn,
            trade_amount_mxn=experiment.trade_amount_mxn,
            fee_rate=experiment.fee_rate,
            start_at=experiment.start_at,
            end_at=experiment.end_at,
            parameters=experiment.parameters,
        )

    def _dataset_id(self, experiment: Experiment) -> str:
        if experiment.dataset_id:
            return experiment.dataset_id
        if not experiment.assets:
            raise ValueError("El experimento requiere al menos un activo.")
        return f"{experiment.assets[0]}/{experiment.timeframe}/default.csv"

    def _require_experiment(self, experiment_id: str) -> Experiment:
        experiment = self.get(experiment_id)
        if experiment is None:
            raise KeyError("Experimento no encontrado.")
        return experiment

    def _validate_experiment(self, experiment: Experiment) -> None:
        if not experiment.name.strip():
            raise ValueError("El nombre del experimento es obligatorio.")
        if not experiment.strategy_name.strip():
            raise ValueError("La estrategia del experimento es obligatoria.")
        if not experiment.assets:
            raise ValueError("El experimento requiere al menos un activo.")
        if experiment.initial_capital_mxn <= 0:
            raise ValueError("El capital inicial debe ser positivo.")
        if experiment.trade_amount_mxn <= 0:
            raise ValueError("El monto por operación debe ser positivo.")


def _metrics_from_backtest(backtest: BacktestResult) -> dict[str, float]:
    if backtest.metrics is None:
        return _zero_metrics()
    metrics = backtest.metrics
    values = {
        "net_profit": float(metrics.final_capital_mxn - metrics.initial_capital_mxn),
        "return": float(metrics.total_return_pct),
        "sharpe": _sharpe(metrics.equity_curve),
        "sortino": _sortino(metrics.equity_curve),
        "calmar": _calmar(
            float(metrics.total_return_pct), float(metrics.max_drawdown_pct)
        ),
        "drawdown": float(metrics.max_drawdown_pct),
        "profit_factor": float(metrics.profit_factor or Decimal("0")),
        "expectancy": float(metrics.expectancy_mxn),
        "win_rate": float(metrics.win_rate_pct),
        "average_trade": float(metrics.average_trade_return_pct),
        "recovery_factor": _recovery_factor(
            float(metrics.final_capital_mxn - metrics.initial_capital_mxn),
            float(metrics.max_drawdown_pct),
        ),
        "trades": float(metrics.trades_count),
    }
    values["stability_score"] = _stability_score(values)
    return values


def _metrics_from_optimization(best: dict[str, Any]) -> dict[str, float]:
    values = _zero_metrics()
    values.update(
        {
            "return": float(best.get("total_return_pct", 0.0)),
            "sharpe": float(best.get("sharpe", 0.0)),
            "drawdown": float(best.get("max_drawdown_pct", 0.0)),
            "profit_factor": float(best.get("profit_factor") or 0.0),
            "win_rate": float(best.get("win_rate_pct", 0.0)),
            "trades": float(best.get("trades_count", 0.0)),
            "stability_score": float(best.get("composite_score", 0.0)),
        }
    )
    return values


def _metrics_from_paper(
    payload: dict[str, Any], initial_capital: float
) -> dict[str, float]:
    equity = float(payload.get("equity_mxn", initial_capital))
    net_profit = equity - initial_capital
    values = _zero_metrics()
    values.update(
        {
            "net_profit": net_profit,
            "return": (net_profit / initial_capital) * 100 if initial_capital else 0.0,
            "drawdown": float(payload.get("max_drawdown_pct", 0.0)),
            "trades": float(len(payload.get("trades", []))),
        }
    )
    values["stability_score"] = _stability_score(values)
    return values


def _zero_metrics() -> dict[str, float]:
    return {
        "net_profit": 0.0,
        "return": 0.0,
        "sharpe": 0.0,
        "sortino": 0.0,
        "calmar": 0.0,
        "drawdown": 0.0,
        "profit_factor": 0.0,
        "expectancy": 0.0,
        "win_rate": 0.0,
        "average_trade": 0.0,
        "recovery_factor": 0.0,
        "stability_score": 0.0,
        "trades": 0.0,
    }


def _rank(results: tuple[ExperimentResult, ...]) -> list[dict[str, Any]]:
    ranked = sorted(results, key=lambda item: _score(item.metrics), reverse=True)
    return [
        {
            "rank": index,
            "experiment_id": item.experiment_id,
            "result_id": item.id,
            "mode": item.mode,
            "score": _finite(_score(item.metrics)),
            "metrics": {key: _finite(value) for key, value in item.metrics.items()},
        }
        for index, item in enumerate(ranked, start=1)
    ]


def _score(metrics: dict[str, float]) -> float:
    return (
        metrics.get("return", 0.0)
        + metrics.get("sharpe", 0.0) * 10
        + metrics.get("sortino", 0.0) * 5
        + metrics.get("calmar", 0.0) * 2
        + metrics.get("profit_factor", 0.0)
        + metrics.get("expectancy", 0.0)
        + metrics.get("win_rate", 0.0) / 10
        + metrics.get("average_trade", 0.0)
        + metrics.get("recovery_factor", 0.0)
        + metrics.get("stability_score", 0.0)
        - metrics.get("drawdown", 0.0)
    )


def _stability_score(metrics: dict[str, float]) -> float:
    return max(
        0.0,
        metrics.get("return", 0.0)
        + metrics.get("win_rate", 0.0) / 10
        + metrics.get("profit_factor", 0.0)
        - metrics.get("drawdown", 0.0),
    )


def _sharpe(equity_curve: tuple[dict[str, Any], ...]) -> float:
    returns = _returns(equity_curve)
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / len(returns)
    return mean / math.sqrt(variance) if variance > 0 else 0.0


def _sortino(equity_curve: tuple[dict[str, Any], ...]) -> float:
    returns = _returns(equity_curve)
    downside = [value for value in returns if value < 0]
    if not returns or not downside:
        return 0.0
    mean = sum(returns) / len(returns)
    downside_variance = sum(value**2 for value in downside) / len(downside)
    return mean / math.sqrt(downside_variance) if downside_variance > 0 else 0.0


def _calmar(total_return: float, drawdown: float) -> float:
    return total_return / drawdown if drawdown > 0 else 0.0


def _recovery_factor(net_profit: float, drawdown: float) -> float:
    return net_profit / drawdown if drawdown > 0 else 0.0


def _returns(equity_curve: tuple[dict[str, Any], ...]) -> list[float]:
    returns: list[float] = []
    previous: float | None = None
    for point in equity_curve:
        equity = float(point.get("equity_mxn", 0.0))
        if previous and previous > 0:
            returns.append((equity - previous) / previous)
        previous = equity
    return returns


def _finite(value: float) -> float:
    return value if math.isfinite(value) else 0.0
