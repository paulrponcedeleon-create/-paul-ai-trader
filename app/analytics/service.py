from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.analytics.ai import AIAttributionEngine
from app.analytics.attribution import AttributionEngine
from app.analytics.broker import BrokerAnalyticsEngine
from app.analytics.equity import EquityCurveEngine
from app.analytics.models import AnalyticsEvent, TradeAnalytics
from app.analytics.performance import PerformanceAnalyticsEngine
from app.analytics.risk import RiskAttributionEngine
from app.brokers.interface import BrokerInterface


class AnalyticsService:
    def __init__(
        self, *, repository: Any | None = None, broker: BrokerInterface | None = None
    ) -> None:
        self.repository = repository
        self.broker_source = broker
        self.performance_engine = PerformanceAnalyticsEngine()
        self.equity_engine = EquityCurveEngine()
        self.attribution_engine = AttributionEngine()
        self.ai_engine = AIAttributionEngine()
        self.risk_engine = RiskAttributionEngine()
        self.broker_engine = BrokerAnalyticsEngine()

    def summary(
        self, trades: list[TradeAnalytics], *, starting_equity: Decimal = Decimal("0")
    ):
        return self.performance_engine.summarize(
            trades, starting_equity=starting_equity
        )

    def equity(
        self, trades: list[TradeAnalytics], *, starting_equity: Decimal = Decimal("0")
    ):
        return self.equity_engine.build(trades, starting_equity=starting_equity)

    def drawdown(
        self, trades: list[TradeAnalytics], *, starting_equity: Decimal = Decimal("0")
    ):
        return self.equity_engine.drawdowns(
            self.equity(trades, starting_equity=starting_equity)
        )

    def strategies(
        self, trades: list[TradeAnalytics], *, starting_equity: Decimal = Decimal("0")
    ):
        return self.attribution_engine.by_strategy(
            trades, starting_equity=starting_equity
        )

    def assets(
        self, trades: list[TradeAnalytics], *, starting_equity: Decimal = Decimal("0")
    ):
        return self.attribution_engine.by_asset(trades, starting_equity=starting_equity)

    def ai(
        self, trades: list[TradeAnalytics], events: list[AnalyticsEvent] | None = None
    ):
        return self.ai_engine.calculate(trades, events)

    def risk(
        self,
        trades: list[TradeAnalytics],
        events: list[AnalyticsEvent] | None = None,
        *,
        equity: Decimal = Decimal("0"),
    ):
        return self.risk_engine.calculate(trades, events, equity=equity)

    def broker(self, events: list[AnalyticsEvent] | None = None):
        return self.broker_engine.calculate(self.broker_source, events)

    def time(self, trades: list[TradeAnalytics], period: str = "day"):
        return self.attribution_engine.time_buckets(trades, period)
