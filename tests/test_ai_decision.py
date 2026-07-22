from __future__ import annotations

import json
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit

from app.ai import (
    AIDecisionEngine,
    ConfidenceEngine,
    DecisionRequest,
    HistoricalMetricsInput,
    IndicatorInput,
    MarketRegimeDetector,
    PaperPortfolioInput,
    StrategySignalInput,
)
from app.reporting.ai_reports import (
    export_confidence_report,
    export_decision_report,
    export_market_regime_report,
)
from app.services.signals import Signal


def signal(
    name: str, action: str, confidence: int = 80, weight: int = 1
) -> StrategySignalInput:
    return StrategySignalInput(
        name, Signal(action, confidence, f"{name} {action}", 100), weight
    )


def request_with(
    signals: tuple[StrategySignalInput, ...],
    closes: tuple[float, ...] = (100, 101, 102, 103, 104, 105),
) -> DecisionRequest:
    return DecisionRequest(
        strategy_signals=signals,
        optimization_results=tuple(),
        historical_metrics=HistoricalMetricsInput(
            total_return_pct=12,
            max_drawdown_pct=5,
            sharpe=1.5,
            profit_factor=2.0,
            win_rate_pct=60,
            stability_pct=70,
        ),
        paper_portfolio=PaperPortfolioInput(
            equity_mxn=10000, cash_mxn=5000, max_drawdown_pct=3
        ),
        indicators=IndicatorInput(closes=closes),
    )


def test_decision_engine_consolidates_buy_sell_hold():
    engine = AIDecisionEngine()
    buy = engine.evaluate(
        request_with(
            (
                signal("momentum", "buy"),
                signal("rsi", "buy"),
                signal("macd", "hold", 50),
            )
        )
    )
    assert buy.action == "buy"
    assert buy.confidence > 50
    assert "momentum" in buy.explanation.strategies_for

    sell = engine.evaluate(
        request_with(
            (
                signal("momentum", "sell"),
                signal("rsi", "sell"),
                signal("macd", "buy", 20),
            )
        )
    )
    assert sell.action == "sell"

    hold = engine.evaluate(
        request_with((signal("momentum", "buy", 50), signal("rsi", "sell", 50)))
    )
    assert hold.action == "hold"


def test_confidence_penalizes_drawdown_and_high_volatility():
    engine = AIDecisionEngine()
    stable = engine.evaluate(
        request_with((signal("momentum", "buy"), signal("rsi", "buy")))
    )
    risky_request = DecisionRequest(
        strategy_signals=(signal("momentum", "buy"), signal("rsi", "buy")),
        historical_metrics=HistoricalMetricsInput(
            max_drawdown_pct=35,
            sharpe=0.2,
            profit_factor=0.5,
            win_rate_pct=30,
            stability_pct=20,
        ),
        paper_portfolio=PaperPortfolioInput(
            equity_mxn=10000, cash_mxn=5000, max_drawdown_pct=20
        ),
        indicators=IndicatorInput(closes=(100, 120, 80, 130, 70, 140)),
    )
    risky = engine.evaluate(risky_request)
    assert risky.confidence < stable.confidence
    assert risky.action in {"hold", "buy"}
    assert risky.explanation.risk_factors


def test_market_regime_detector_returns_expected_regimes():
    detector = MarketRegimeDetector()
    assert detector.detect(
        IndicatorInput(closes=(100, 101, 102, 103, 104, 105, 106))
    ) in {"bull", "low_volatility"}
    assert detector.detect(
        IndicatorInput(closes=(106, 105, 104, 103, 102, 101, 100))
    ) in {"bear", "low_volatility"}
    assert (
        detector.detect(IndicatorInput(closes=(100, 130, 70, 140, 60, 150)))
        == "high_volatility"
    )
    assert (
        detector.detect(IndicatorInput(closes=(100, 100, 100, 100, 100)))
        == "low_volatility"
    )


def test_decision_score_uses_optimizer_paper_and_risk_inputs():
    class Result:
        composite_score = Decimal("50")
        total_return_pct = Decimal("10")
        max_drawdown_pct = Decimal("2")
        sharpe = Decimal("1")
        profit_factor = Decimal("2")
        win_rate_pct = Decimal("60")
        trades_count = 3
        strategy_name = "momentum"
        strategy_version = "1.0"
        parameters = {}
        backtest_status = "completed"

    engine = AIDecisionEngine()
    decision = engine.evaluate(
        DecisionRequest(
            strategy_signals=(signal("momentum", "buy"), signal("ema", "buy")),
            optimization_results=(Result(),),
            historical_metrics=HistoricalMetricsInput(
                total_return_pct=20,
                max_drawdown_pct=2,
                sharpe=2,
                profit_factor=2,
                win_rate_pct=70,
            ),
            paper_portfolio=PaperPortfolioInput(equity_mxn=10000, cash_mxn=8000),
            indicators=IndicatorInput(closes=(100, 101, 102, 103, 104, 105)),
        )
    )
    assert decision.score > Decimal("50")


def test_explanation_and_reports_are_deterministic_json():
    decision = AIDecisionEngine().evaluate(
        request_with((signal("momentum", "buy"), signal("rsi", "buy")))
    )
    decision_report = json.loads(export_decision_report(decision))
    confidence_report = json.loads(export_confidence_report(decision))
    regime_report = json.loads(export_market_regime_report(decision))
    assert decision_report["explanation"]["primary_reason"]
    assert confidence_report["confidence"] == decision.confidence
    assert regime_report["market_regime"] == decision.market_regime


def test_confidence_engine_bounds_values():
    confidence = ConfidenceEngine().calculate(
        request_with((signal("momentum", "buy"),)), "bull", Decimal("100")
    )
    assert 0 <= confidence <= 100
