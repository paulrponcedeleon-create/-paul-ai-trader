from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from app.experiments import ExperimentManager
from app.reporting.research_reports import (
    export_research_csv,
    export_research_html,
    export_research_json,
    export_research_markdown,
)
from app.research.manager import (
    ResearchManager,
    correlation_matrix,
    monte_carlo_simulation,
    robustness_metrics,
)
from app.services.historical_data import HistoricalCandle, HistoricalDataset

pytestmark = pytest.mark.unit


class FakeHistoricalProvider:
    def __init__(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        prices = [100, 102, 104, 103, 99, 97, 101, 105, 108, 106, 109, 111]
        candles = [
            HistoricalCandle(
                start + timedelta(minutes=index),
                price,
                price + 1,
                price - 1,
                price,
                10,
            )
            for index, price in enumerate(prices)
        ]
        self.dataset = HistoricalDataset(
            "btc_mxn",
            "1m",
            "default",
            candles[0].timestamp,
            candles[-1].timestamp,
            tuple(candles),
            {"dataset_id": "btc_mxn/1m/default.csv"},
        )

    def list_datasets(self):
        return ["btc_mxn/1m/default.csv"]

    def load_dataset(self, dataset_id):
        assert dataset_id == "btc_mxn/1m/default.csv"
        return self.dataset

    def get_candles(self, dataset_id, start_at=None, end_at=None):
        return list(self.load_dataset(dataset_id).candles)

    def validate_dataset(self, dataset_id):
        self.load_dataset(dataset_id)


def _manager():
    return ResearchManager(
        ExperimentManager(historical_data_provider=FakeHistoricalProvider())
    )


def test_monte_carlo_is_reproducible_and_reports_distribution():
    first = monte_carlo_simulation([1.0, -0.5, 2.0], seed=11, iterations=20)
    second = monte_carlo_simulation([1.0, -0.5, 2.0], seed=11, iterations=20)

    assert first.to_public_dict() == second.to_public_dict()
    assert first.iterations == 20
    assert first.worst_case <= first.best_case
    assert 0 <= first.probability_of_loss <= 1


def test_correlation_matrix_handles_portfolio_series():
    matrix = correlation_matrix({"a": [1, 2, 3], "b": [1, 2, 3], "c": [3, 2, 1]})

    assert matrix["a"]["a"] == 1.0
    assert matrix["a"]["b"] == pytest.approx(1.0)
    assert matrix["a"]["c"] < 0


def test_research_manager_runs_mass_validation_and_builds_portfolio():
    run = _manager().start(
        {
            "strategies": ["momentum"],
            "assets": ["btc_mxn"],
            "timeframes": ["1m"],
            "capitals": [10000, 12000],
            "parameter_sets": [{"window": 2}, {"window": 3}],
            "dataset_id": "btc_mxn/1m/default.csv",
            "mode": "backtest",
            "monte_carlo_seed": 5,
            "monte_carlo_iterations": 15,
        }
    )
    data = run.to_public_dict()

    assert data["status"] == "completed"
    assert len(data["results"]) == 4
    assert data["ranking"][0]["rank_score"] >= data["ranking"][-1]["rank_score"]
    assert "momentum" in data["portfolio"]["strategy_weights"]
    assert data["recommendations"]


def test_research_robustness_and_reports_are_serializable():
    manager = _manager()
    run = manager.start(
        {
            "strategies": ["momentum"],
            "parameter_sets": [{"window": 2}, {"window": 4}],
            "dataset_id": "btc_mxn/1m/default.csv",
            "monte_carlo_iterations": 10,
        }
    )
    result = run.results[0].experiment_result
    robust = robustness_metrics(
        result, [item.experiment_result for item in run.results]
    )

    assert robust["robustness"] >= 0
    parsed = json.loads(export_research_json(run))
    assert parsed["status"] == "completed"
    assert "experiment_id" in export_research_csv(run)
    assert "# Portfolio Research Report" in export_research_markdown(run)
    assert "<h1>Portfolio Research Report</h1>" in export_research_html(run)
