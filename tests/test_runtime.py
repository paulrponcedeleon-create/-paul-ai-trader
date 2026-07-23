from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit

from app.ai.decision_engine import DecisionExplanation, DecisionResult
from app.market_data.models import Candle, ProviderStatus
from app.paper_trading.risk import RiskDecision
from app.runtime import RuntimeConfig, RuntimeEngine
from app.services.signals import Signal


class FakeProvider:
    name = "fake"

    def __init__(self):
        self.connected = False
        self.disconnects = 0

    async def connect(self):
        self.connected = True
        return self.status()

    async def disconnect(self):
        self.connected = False
        self.disconnects += 1
        return self.status()

    def status(self):
        return ProviderStatus("fake", self.connected, True, False, tuple(), 0, None)

    async def subscribe(self, book, channels=("ticker",)):
        return self.status()

    async def get_ticker(self, book):
        raise NotImplementedError

    async def get_orderbook(self, book):
        raise NotImplementedError

    async def get_recent_trades(self, book, limit=100):
        return []

    async def get_candles(self, book, timeframe="1m", limit=100):
        return [
            Candle(
                book,
                timeframe,
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                Decimal("100"),
                Decimal("102"),
                Decimal("99"),
                Decimal("101"),
                Decimal("10"),
            )
        ]


class BuyStrategy:
    def generate_signal(self, history):
        return Signal("buy", 100, "test buy", float(history[-1].close))


class FakeStrategyFactory:
    def create(self, *args, **kwargs):
        return BuyStrategy()


class BuyAI:
    def evaluate(self, request):
        return DecisionResult(
            "buy",
            100,
            Decimal("100"),
            "bull",
            DecisionExplanation(("test",), tuple(), tuple(), 100, "buy"),
        )


class RejectAllRisk:
    def __init__(self):
        self.calls = []

    def evaluate_open(self, **kwargs):
        self.calls.append(kwargs)
        return RiskDecision(False, "Bloqueada por política de riesgo de prueba.")


class UnexpectedExecution:
    def __init__(self):
        self.calls = 0

    def execute(self, request):
        self.calls += 1
        raise AssertionError("Una orden rechazada no debe llegar al motor de ejecución.")


def test_runtime_cycle_market_strategy_ai_broker_portfolio_system():
    runtime = RuntimeEngine(
        config=RuntimeConfig(
            books=("btc_mxn",), trade_amount_mxn=Decimal("100"), max_history=2
        ),
        market_data=FakeProvider(),
        strategy_factory=FakeStrategyFactory(),
        ai_engine=BuyAI(),
    )
    status = asyncio.run(runtime.run_cycles(3))

    assert status.running is True
    assert status.cycles == 3
    assert runtime.last_decision["action"] == "buy"
    assert runtime.last_order["status"] in {"filled", "rejected"}
    assert len(runtime.history["btc_mxn"]) <= 2
    assert runtime.components()["broker"]["mode"] == "paper"
    assert runtime.system.events.list()


def test_runtime_records_risk_rejection_without_calling_execution_or_broker():
    risk = RejectAllRisk()
    execution = UnexpectedExecution()
    runtime = RuntimeEngine(
        config=RuntimeConfig(books=("btc_mxn",), max_history=2),
        market_data=FakeProvider(),
        strategy_factory=FakeStrategyFactory(),
        ai_engine=BuyAI(),
        risk_manager=risk,
        execution_engine=execution,
    )

    status = asyncio.run(runtime.run_cycles(1))

    assert len(risk.calls) == 1
    assert execution.calls == 0
    assert runtime.broker.get_orders() == []
    assert status.last_order == {
        "id": "runtime-risk-1-btc_mxn",
        "book": "btc_mxn",
        "side": "buy",
        "type": "market",
        "status": "rejected",
        "amount_mxn": 100.0,
        "price": 101.0,
        "created_at": None,
        "reason": "Bloqueada por política de riesgo de prueba.",
    }


def test_runtime_stop_is_clean_and_disconnects_provider():
    provider = FakeProvider()
    runtime = RuntimeEngine(
        market_data=provider, strategy_factory=FakeStrategyFactory(), ai_engine=BuyAI()
    )
    asyncio.run(runtime.start())
    stopped = asyncio.run(runtime.stop())
    assert stopped.running is False
    assert provider.disconnects == 1
