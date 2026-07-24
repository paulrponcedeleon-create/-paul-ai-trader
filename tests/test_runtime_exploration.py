from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from app.ai.decision_engine import DecisionExplanation, DecisionResult
from app.market_data.models import Candle, ProviderStatus
from app.paper_trading.exploration import ExplorationConfig
from app.paper_trading.risk import RiskDecision
from app.runtime import RuntimeConfig
from app.runtime_exploration import ExplorationRuntimeEngine
from app.services.signals import Signal


class HoldProvider:
    name = "hold-provider"

    def __init__(self):
        self.connected = False
        self.tick = 0

    async def connect(self):
        self.connected = True
        return self.status()

    async def disconnect(self):
        self.connected = False
        return self.status()

    def status(self):
        return ProviderStatus(
            self.name,
            self.connected,
            True,
            False,
            tuple(),
            0,
            None,
        )

    async def get_candles(self, book, timeframe="1m", limit=100):
        self.tick += 1
        return [
            Candle(
                book,
                timeframe,
                datetime(2026, 7, 24, 12, self.tick % 60, tzinfo=timezone.utc),
                Decimal("100"),
                Decimal("101"),
                Decimal("99"),
                Decimal("100"),
                Decimal("10"),
            )
        ]


class HoldStrategy:
    def generate_signal(self, history):
        return Signal("hold", 50, "test hold", float(history[-1].close))


class HoldStrategyFactory:
    def create(self, *args, **kwargs):
        return HoldStrategy()


class HoldAI:
    def evaluate(self, request):
        return DecisionResult(
            "hold",
            60,
            Decimal("55"),
            "sideways",
            DecisionExplanation(tuple(), tuple(), tuple(), 60, "hold"),
        )


class RejectExplorationRisk:
    def evaluate_open(self, **kwargs):
        return RiskDecision(False, "Exploración bloqueada por riesgo de prueba.")


def _runtime(*, live=False, risk_manager=None):
    return ExplorationRuntimeEngine(
        config=RuntimeConfig(
            books=("btc_mxn",),
            max_history=20,
            min_trade_amount_mxn=Decimal("10"),
        ),
        exploration_config=ExplorationConfig(
            enabled=True,
            hold_cycles_before_entry=2,
            max_holding_cycles=2,
            cooldown_cycles=3,
            amount_mxn=Decimal("10"),
        ),
        live_trading=live,
        market_data=HoldProvider(),
        strategy_factory=HoldStrategyFactory(),
        ai_engine=HoldAI(),
        risk_manager=risk_manager,
    )


def test_hold_to_buy_follow_and_sell_is_a_complete_paper_experience():
    runtime = _runtime()

    status = asyncio.run(runtime.run_cycles(4))

    orders = runtime.broker.get_orders()
    assert [order.side for order in orders] == ["buy", "sell"]
    assert orders[0].reason == "paper_exploration_hold_streak"
    assert orders[1].reason == "paper_exploration_timeout"
    assert runtime.broker.get_positions() == []
    assert status.exploration["entries"] == 1
    assert status.exploration["exits"] == 1
    assert status.exploration["active_positions"] == 0
    assert status.exploration["metrics_separate_from_strategy"] is True
    assert runtime.last_order["source"] == "exploration"


def test_exploration_buy_still_requires_risk_approval():
    runtime = _runtime(risk_manager=RejectExplorationRisk())

    status = asyncio.run(runtime.run_cycles(2))

    assert runtime.broker.get_orders() == []
    assert status.exploration["entries"] == 0
    assert status.exploration["rejected"] == 1
    assert status.last_order["status"] == "rejected"


def test_live_mode_blocks_exploration_even_when_setting_is_enabled():
    runtime = _runtime(live=True)

    status = asyncio.run(runtime.run_cycles(5))

    assert runtime.broker.get_orders() == []
    assert status.exploration["enabled"] is False
    assert status.exploration["live_trading_blocked"] is True


def test_runtime_status_api_exposes_separate_exploration_metrics(client):
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200
    response = client.get("/runtime/status")

    assert response.status_code == 200
    exploration = response.json()["exploration"]
    assert exploration["enabled"] is True
    assert exploration["metrics_separate_from_strategy"] is True
    assert exploration["amount_mxn"] == 10.0


def test_dashboard_exposes_exploration_status_labels(client):
    response = client.get("/static/dashboard-v2.js")

    assert response.status_code == 200
    assert "Experiencia exploratoria" in response.text
    assert "HOLD consecutivos" in response.text
    assert "Experiencias cerradas" in response.text
