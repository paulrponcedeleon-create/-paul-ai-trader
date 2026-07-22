from __future__ import annotations

import json

import pytest

from app.adaptive import (
    AdaptiveManager,
    MarketRegimeDetector,
    PortfolioAllocator,
    StrategyProfile,
    StrategyRegistry,
    StrategySelector,
)
from app.reporting.adaptive_reports import (
    export_adaptive_csv,
    export_adaptive_html,
    export_adaptive_json,
    export_adaptive_markdown,
)

pytestmark = pytest.mark.unit


def _profile(name: str, *, returns=(4.0, 5.0, 6.0), drawdown=2.0, observed=5.5):
    return StrategyProfile(
        name=name,
        performance_history=tuple(returns),
        robustness_metrics={"robustness": 8.0, "consistency": 0.8},
        recent_drawdown_pct=drawdown,
        sharpe=1.2,
        profit_factor=1.5,
        stability=7.0,
        compatible_assets=("btc_mxn",),
        compatible_timeframes=("1m",),
        expected_return_pct=sum(returns) / len(returns),
        observed_return_pct=observed,
    )


def test_market_regime_detector_is_deterministic():
    detector = MarketRegimeDetector()

    assert detector.detect((100, 102, 104, 106)) == "bullish_trend"
    assert detector.detect((100, 98, 96, 94)) == "bearish_trend"
    assert detector.detect((100, 100.05, 100.02, 100.01)) == "low_volatility"
    assert detector.detect((100, 110, 90, 115)) == "high_volatility"


def test_strategy_selection_filters_and_ranks_by_regime_and_quality():
    registry = StrategyRegistry()
    registry.upsert(_profile("momentum", returns=(5, 6, 7), drawdown=1.0))
    registry.upsert(_profile("weak", returns=(-1, -2, -3), drawdown=15.0, observed=-3))
    registry.upsert(
        StrategyProfile(
            "other_asset",
            (10.0,),
            {"robustness": 10.0, "consistency": 1.0},
            1.0,
            2.0,
            2.0,
            10.0,
            ("eth_mxn",),
            ("1m",),
        )
    )

    selection = StrategySelector().select(
        registry.list(),
        regime="bullish_trend",
        asset="btc_mxn",
        timeframe="1m",
        top_n=1,
    )

    assert selection.selected[0].name == "momentum"
    assert selection.ranking[0]["score"] >= selection.ranking[-1]["score"]
    assert all(row["strategy"] != "other_asset" for row in selection.ranking)


def test_portfolio_allocator_methods_and_caps_weights():
    selection = StrategySelector().select(
        [_profile("a"), _profile("b", returns=(1, 2, 3), drawdown=4)],
        regime="sideways",
        asset="btc_mxn",
        timeframe="1m",
        top_n=2,
    )
    allocation = PortfolioAllocator().allocate(
        selection, method="score", max_weight=0.6
    )
    risk_allocation = PortfolioAllocator().allocate(
        selection, method="risk", max_weight=0.7
    )

    assert round(sum(allocation.weights.values()), 6) == 1.0
    assert max(allocation.weights.values()) <= 0.6
    assert round(sum(risk_allocation.weights.values()), 6) == 1.0


def test_adaptive_manager_loads_research_tracks_degradation_and_reports():
    manager = AdaptiveManager()
    manager.registry.upsert(_profile("momentum", observed=-2.0))
    selection = manager.selection(
        closes=(100, 101, 102, 103), asset="btc_mxn", timeframe="1m"
    )
    portfolio = manager.portfolio(method="equal", max_weight=1.0)
    report = manager.report()

    assert selection.regime == "bullish_trend"
    assert portfolio.weights["momentum"] == 1.0
    assert (
        "performance_degradation:momentum" in report["performance_tracking"]["alerts"]
    )
    assert (
        json.loads(export_adaptive_json(report))["selection"]["regime"]
        == "bullish_trend"
    )
    assert "momentum" in export_adaptive_csv(report)
    assert "# Adaptive Portfolio Report" in export_adaptive_markdown(report)
    assert "<h1>Adaptive Portfolio Report</h1>" in export_adaptive_html(report)
