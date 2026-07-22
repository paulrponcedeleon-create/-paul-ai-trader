from __future__ import annotations

import json

import pytest

from app.reporting.validation_reports import (
    export_validation_csv,
    export_validation_html,
    export_validation_json,
    export_validation_markdown,
)
from app.validation import ValidationManager, ValidationRules

pytestmark = pytest.mark.unit


def _research_run():
    return {
        "results": [
            {
                "experiment_result": {
                    "payload": {"strategy_name": "momentum"},
                    "metrics": {"return": 8.0},
                },
                "robustness": {"robustness": 8.0, "consistency": 0.8},
            },
            {
                "experiment_result": {
                    "payload": {"strategy_name": "mean_reversion"},
                    "metrics": {"return": 6.0},
                },
                "robustness": {"robustness": 7.0, "consistency": 0.7},
            },
        ]
    }


def test_validation_promotes_strategy_that_matches_rules():
    manager = ValidationManager()

    run = manager.run(
        research_run=_research_run(),
        paper_observations=[
            {
                "strategy": "momentum",
                "observed_return_pct": 9.0,
                "drawdown_pct": 4.0,
                "sharpe": 1.4,
                "profit_factor": 1.8,
                "win_rate": 58.0,
                "trades": 120,
                "stability": 8.0,
                "active_days": 45,
            }
        ],
    )

    assert run.promotions[0].strategy == "momentum"
    assert run.retirements == ()
    assert manager.status()["active_strategies"] == ["momentum"]


def test_validation_retires_degraded_strategy():
    manager = ValidationManager()

    run = manager.run(
        research_run=_research_run(),
        paper_observations=[
            {
                "strategy": "mean_reversion",
                "observed_return_pct": -12.0,
                "drawdown_pct": 25.0,
                "sharpe": 0.1,
                "profit_factor": 0.7,
                "win_rate": 35.0,
                "trades": 130,
                "stability": 2.0,
                "active_days": 40,
            }
        ],
    )

    result = run.results[0]
    assert result.deviation_pct == -18.0
    assert "expected_observed_deviation" in result.alerts
    assert run.retirements[0].reason == "excessive_drawdown"
    assert manager.retirements()[0]["strategy"] == "mean_reversion"


def test_validation_rules_are_configurable():
    rules = ValidationRules(min_active_days=1, min_trades=1, min_sharpe=0.5)
    manager = ValidationManager(rules)

    run = manager.run(
        research_run=_research_run(),
        paper_observations=[
            {
                "strategy": "momentum",
                "observed_return_pct": 8.0,
                "drawdown_pct": 2.0,
                "sharpe": 0.6,
                "profit_factor": 1.1,
                "win_rate": 51.0,
                "trades": 2,
                "stability": 5.0,
                "active_days": 2,
            }
        ],
        rules={"min_consistency": 0.7, "min_robustness": 7.0},
    )

    assert run.rules.min_trades == 100
    assert run.promotions == ()


def test_validation_report_exporters_are_deterministic():
    manager = ValidationManager()
    manager.run(
        research_run=_research_run(),
        paper_observations=[
            {
                "strategy": "momentum",
                "observed_return_pct": 9.0,
                "drawdown_pct": 4.0,
                "sharpe": 1.4,
                "profit_factor": 1.8,
                "win_rate": 58.0,
                "trades": 120,
                "stability": 8.0,
                "active_days": 45,
            }
        ],
    )
    report = manager.report()

    assert (
        json.loads(export_validation_json(report))["promotions"][0]["strategy"]
        == "momentum"
    )
    assert "momentum" in export_validation_csv(report)
    assert "# Validation Promotion Pipeline Report" in export_validation_markdown(
        report
    )
    assert "<h1>Validation Promotion Pipeline Report</h1>" in export_validation_html(
        report
    )
