from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json

import pytest

pytestmark = pytest.mark.unit

from app.optimization.engine import OptimizationEngine, OptimizationRequest
from app.optimization.parameter_space import ParameterSpace, ParameterSpaceError
from app.optimization.ranking import RankingEngine
from app.optimization.search import GridSearchOptimizer, RandomSearchOptimizer
from app.reporting.optimization_reports import (
    export_optimization_csv,
    export_optimization_json,
    export_optimization_markdown,
)
from app.services.backtesting import BacktestEngine
from app.services.historical_data import HistoricalCandle, HistoricalDataset
from app.strategies.factory import StrategyFactory


@dataclass
class Provider:
    dataset: HistoricalDataset

    def list_datasets(self):
        return [self.dataset.metadata["dataset_id"]]

    def load_dataset(self, dataset_id: str):
        assert dataset_id == self.dataset.metadata["dataset_id"]
        return self.dataset

    def get_candles(self, dataset_id: str, start_at=None, end_at=None):
        return list(self.load_dataset(dataset_id).candles)

    def validate_dataset(self, dataset_id: str):
        self.load_dataset(dataset_id)


def dataset() -> HistoricalDataset:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    closes = [100, 101, 102, 103, 99, 98, 104, 106, 105, 107, 108, 104, 110, 112, 109]
    candles = tuple(
        HistoricalCandle(
            start + timedelta(days=index), close - 1, close + 1, close - 2, close, 10
        )
        for index, close in enumerate(closes)
    )
    return HistoricalDataset(
        "btc_mxn",
        "1d",
        "test",
        candles[0].timestamp,
        candles[-1].timestamp,
        candles,
        {"dataset_id": "btc_mxn/1d/test.csv"},
    )


def test_parameter_space_validates_and_generates_all_combinations():
    space = ParameterSpace.from_dict({"fast": [5, 10], "slow": [20, 30]})
    assert GridSearchOptimizer().generate(space) == (
        {"fast": 5, "slow": 20},
        {"fast": 5, "slow": 30},
        {"fast": 10, "slow": 20},
        {"fast": 10, "slow": 30},
    )
    with pytest.raises(ParameterSpaceError):
        ParameterSpace.from_dict({"window": [5, 5]})


def test_parameter_space_validates_against_strategy_schema():
    ParameterSpace.from_dict({"window": [5, 10]}).validate_for_strategy(
        StrategyFactory(), "momentum", "1.0"
    )
    with pytest.raises(ValueError):
        ParameterSpace.from_dict({"unknown": [1]}).validate_for_strategy(
            StrategyFactory(), "momentum", "1.0"
        )
    with pytest.raises(ValueError):
        ParameterSpace.from_dict({"fast": [10], "slow": [5]}).validate_for_strategy(
            StrategyFactory(), "ema_cross", "1.0"
        )


def test_random_search_is_reproducible_and_limited():
    space = ParameterSpace.from_dict({"fast": [5, 10, 15], "slow": [20, 30]})
    first = RandomSearchOptimizer(seed=7, max_iterations=3).generate(space)
    second = RandomSearchOptimizer(seed=7, max_iterations=3).generate(space)
    assert first == second
    assert len(first) == 3


def test_optimization_engine_uses_backtest_engine_and_ranks_results():
    provider = Provider(dataset())
    backtest_engine = BacktestEngine(historical_data_provider=provider)
    space = ParameterSpace.from_dict({"window": [2, 3, 4]})
    report = OptimizationEngine(backtest_engine=backtest_engine).run(
        OptimizationRequest(
            dataset_id="btc_mxn/1d/test.csv",
            strategy_name="momentum",
            strategy_version="1.0",
            initial_capital_mxn=1000,
            trade_amount_mxn=100,
            fee_rate=0.001,
            parameter_space=space,
        ),
        GridSearchOptimizer().generate(space),
    )
    assert report.status == "completed"
    assert len(report.results) == 3
    ranked = RankingEngine().top(list(report.results), 2)
    assert ranked[0].composite_score >= ranked[1].composite_score
    assert RankingEngine().bottom(list(report.results), 1)


def test_strategy_comparison_selects_best_result_across_strategies():
    provider = Provider(dataset())
    backtest_engine = BacktestEngine(historical_data_provider=provider)
    results = []
    for name, space in {
        "momentum": ParameterSpace.from_dict({"window": [2]}),
        "ema_cross": ParameterSpace.from_dict({"fast": [2], "slow": [4]}),
        "rsi": ParameterSpace.from_dict(
            {"period": [3], "oversold": [35], "overbought": [65]}
        ),
    }.items():
        report = OptimizationEngine(backtest_engine=backtest_engine).run(
            OptimizationRequest(
                "btc_mxn/1d/test.csv", name, "1.0", 1000, 100, 0.001, space
            ),
            GridSearchOptimizer().generate(space),
        )
        results.extend(report.results)
    best = RankingEngine().top(results, 1)[0]
    assert best.strategy_name in {"momentum", "ema_cross", "rsi"}
    assert best.parameters


def test_optimization_exporters_are_serializable_and_readable():
    provider = Provider(dataset())
    backtest_engine = BacktestEngine(historical_data_provider=provider)
    space = ParameterSpace.from_dict({"window": [2, 3]})
    report = OptimizationEngine(backtest_engine=backtest_engine).run(
        OptimizationRequest(
            "btc_mxn/1d/test.csv", "momentum", "1.0", 1000, 100, 0.001, space
        ),
        GridSearchOptimizer().generate(space),
    )
    data = json.loads(export_optimization_json(report))
    assert data["executive_summary"]
    assert "score" in export_optimization_csv(report)
    assert "Top 10" in export_optimization_markdown(report)
