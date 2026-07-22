from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest

pytestmark = pytest.mark.unit

from app.analytics import AnalyticsEvent, AnalyticsService, TradeAnalytics
from app.analytics.ai import AIAttributionEngine
from app.analytics.broker import BrokerAnalyticsEngine
from app.analytics.equity import EquityCurveEngine
from app.analytics.performance import PerformanceAnalyticsEngine
from app.analytics.risk import RiskAttributionEngine
from app.brokers import PaperBroker
from app.reporting.analytics_reports import (
    export_analytics_csv,
    export_analytics_html,
    export_analytics_json,
    export_analytics_markdown,
)


def t(
    i: int,
    pnl: Decimal,
    strategy: str = "momentum",
    asset: str = "btc_mxn",
    reason: str = "take_profit",
) -> TradeAnalytics:
    opened = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)
    closed = opened + timedelta(hours=2)
    return TradeAnalytics(
        str(i),
        asset,
        strategy,
        "buy",
        Decimal("100"),
        Decimal("110"),
        Decimal("1"),
        Decimal("100"),
        Decimal("1"),
        Decimal("1"),
        Decimal("2"),
        pnl + Decimal("2"),
        pnl,
        pnl,
        timedelta(hours=2),
        reason,
        ai_decision="buy",
        ai_confidence=80 if pnl > 0 else 30,
        market_regime="bull",
        broker="paper",
        opened_at=opened,
        closed_at=closed,
    )


def sample_trades() -> list[TradeAnalytics]:
    return [
        t(0, Decimal("10")),
        t(1, Decimal("-5"), strategy="rsi", asset="eth_mxn", reason="stop_loss"),
        t(2, Decimal("0")),
    ]


def test_performance_summary_known_values_and_empty_lists():
    engine = PerformanceAnalyticsEngine()
    summary = engine.summarize(sample_trades(), starting_equity=Decimal("100"))
    assert summary.net_profit == Decimal("5.0000")
    assert summary.gross_profit == Decimal("10.0000")
    assert summary.gross_loss == Decimal("5.0000")
    assert summary.profit_factor == Decimal("2.0000")
    assert summary.expectancy == Decimal("1.6667")
    assert summary.payoff_ratio == Decimal("2.0000")
    assert summary.total_trades == 3
    assert (
        engine.summarize([], starting_equity=0).to_public_dict()["profit_factor"] == 0.0
    )


def test_equity_curve_drawdown_and_recovery_are_deterministic():
    points = EquityCurveEngine().build(sample_trades(), starting_equity=Decimal("100"))
    assert [point.equity for point in points] == [
        Decimal("110"),
        Decimal("105"),
        Decimal("105"),
    ]
    drawdowns = EquityCurveEngine().drawdowns(points)
    assert drawdowns
    assert drawdowns[-1].recovered is False


def test_strategy_asset_time_and_filters():
    service = AnalyticsService()
    trades = sample_trades()
    assert service.strategies(trades)[0].strategy == "momentum"
    assert {item.asset for item in service.assets(trades)} == {"btc_mxn", "eth_mxn"}
    assert service.time(trades, "day")[0].trades == 1
    filtered = service.performance_engine.filter_trades(
        trades, asset="eth_mxn", close_reason="stop_loss"
    )
    assert len(filtered) == 1


def test_ai_risk_and_broker_attribution():
    events = [
        AnalyticsEvent(
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            "risk",
            "blocked",
            "warning",
            "risk",
            "limit",
            {"risk": "WARNING"},
        ),
        AnalyticsEvent(
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            "broker",
            "accepted",
            "info",
            "paper",
            "accepted",
            {"latency_ms": 2},
        ),
    ]
    ai = AIAttributionEngine().calculate(sample_trades(), events)
    assert ai[0].decision == "buy"
    risk = RiskAttributionEngine().calculate(
        sample_trades(), events, equity=Decimal("1000")
    )
    assert risk.blocked_operations == 1
    broker = BrokerAnalyticsEngine().calculate(PaperBroker(), events)
    assert broker.accepted_orders == 1


def test_reports_escape_and_serialize_all_formats():
    service = AnalyticsService()
    trades = sample_trades()
    report = {
        "summary": service.summary(trades).to_public_dict(),
        "equity": [p.to_public_dict() for p in service.equity(trades)],
        "drawdown": [d.to_public_dict() for d in service.drawdown(trades)],
        "strategies": [s.to_public_dict() for s in service.strategies(trades)],
        "assets": [a.to_public_dict() for a in service.assets(trades)],
        "ai": [a.to_public_dict() for a in service.ai(trades)],
        "risk": service.risk(trades).to_public_dict(),
        "broker": service.broker().to_public_dict(),
        "best_trades": [trades[0].to_public_dict()],
        "worst_trades": [trades[1].to_public_dict()],
    }
    assert json.loads(export_analytics_json(report))["summary"]
    assert "summary" in export_analytics_csv(report)
    assert "Analytics Report" in export_analytics_markdown(report)
    assert "<script" not in export_analytics_html({"summary": {"x": "<script>"}})
