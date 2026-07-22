from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest

from app.experiments import Experiment, ExperimentManager
from app.reporting.experiment_reports import (
    export_experiment_csv,
    export_experiment_html,
    export_experiment_json,
    export_experiment_markdown,
)
from app.services.historical_data import HistoricalCandle, HistoricalDataset

pytestmark = pytest.mark.unit


class FakeHistoricalProvider:
    def __init__(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        candles = []
        prices = [100, 101, 102, 101, 99, 98, 100, 103, 105, 104]
        for index, price in enumerate(prices):
            candles.append(
                HistoricalCandle(
                    start + timedelta(minutes=index),
                    price,
                    price + 1,
                    price - 1,
                    price,
                    10,
                )
            )
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
        candles = list(self.load_dataset(dataset_id).candles)
        if start_at:
            candles = [item for item in candles if item.timestamp >= start_at]
        if end_at:
            candles = [item for item in candles if item.timestamp <= end_at]
        return candles

    def validate_dataset(self, dataset_id):
        self.load_dataset(dataset_id)


def _experiment(**overrides):
    data = {
        "name": "Momentum Lab",
        "description": "Reproducible momentum experiment",
        "strategy_name": "momentum",
        "parameters": {"window": 2},
        "assets": ("btc_mxn",),
        "timeframe": "1m",
        "initial_capital_mxn": Decimal("10000"),
        "trade_amount_mxn": Decimal("1000"),
        "fee_rate": Decimal("0.001"),
        "dataset_id": "btc_mxn/1m/default.csv",
        "risk_config": {"training_window_days": 1, "validation_window_days": 1},
        "parameter_space": {"window": (2, 3)},
    }
    data.update(overrides)
    return Experiment(**data)


def test_experiment_creation_and_backtest_run_are_persisted():
    manager = ExperimentManager(historical_data_provider=FakeHistoricalProvider())
    experiment = manager.create(_experiment())
    run = manager.run(experiment.id, "backtest")

    assert manager.get(experiment.id) == experiment
    assert len(manager.list()) == 1
    assert run.result.status == "completed"
    assert run.result.metrics["trades"] >= 0
    assert manager.compare().best_experiment_id == experiment.id


def test_experiment_optimization_and_paper_replay_reuse_existing_engines():
    manager = ExperimentManager(historical_data_provider=FakeHistoricalProvider())
    experiment = manager.create(_experiment())

    optimization = manager.run(experiment.id, "optimization")
    paper = manager.run(experiment.id, "paper_replay")
    comparison = manager.compare((experiment.id,)).to_public_dict()

    assert optimization.result.status == "completed"
    assert optimization.result.payload["results"]
    assert paper.result.status == "completed"
    assert "equity_mxn" in paper.result.payload
    assert comparison["ranking"][0]["experiment_id"] == experiment.id


def test_experiment_walk_forward_reports_missing_dates_as_failed():
    manager = ExperimentManager(historical_data_provider=FakeHistoricalProvider())
    experiment = manager.create(_experiment(start_at=None, end_at=None))
    run = manager.run(experiment.id, "walk_forward")

    assert run.result.status == "failed"
    assert "requiere start_at" in run.result.payload["error"]


def test_experiment_reports_export_comparison_formats():
    manager = ExperimentManager(historical_data_provider=FakeHistoricalProvider())
    experiment = manager.create(_experiment())
    manager.run(experiment.id, "backtest")
    comparison = manager.compare()

    parsed = json.loads(export_experiment_json(comparison))
    assert parsed["best_experiment_id"] == experiment.id
    assert "experiment_id" in export_experiment_csv(comparison)
    assert "# Strategy Lab Experiment Report" in export_experiment_markdown(comparison)
    assert "<h1>Strategy Lab Experiment Report</h1>" in export_experiment_html(
        comparison
    )
