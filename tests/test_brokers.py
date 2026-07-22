from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit

from app.ai import DecisionExplanation, DecisionResult
from app.brokers import (
    BitsoBroker,
    BrokerFactory,
    BrokerInterface,
    ExecutionEngine,
    ExecutionRequest,
    LiveTradingDisabledError,
    PaperBroker,
)
from app.reporting.broker_reports import (
    export_broker_status_json,
    export_broker_status_markdown,
)


def test_paper_broker_implements_interface_and_health():
    broker = PaperBroker(initial_cash_mxn=1000)
    assert isinstance(broker, BrokerInterface)
    assert broker.health().connected is False
    health = broker.connect()
    assert health.connected is True
    assert health.mode == "paper"
    assert health.live_enabled is False
    assert broker.disconnect().connected is False


def test_paper_broker_places_simulated_orders_without_external_services():
    broker = PaperBroker(initial_cash_mxn=1000)
    broker.connect()
    buy = broker.place_market_buy(
        book="btc_mxn", amount_mxn=Decimal("100"), price=Decimal("50")
    )
    assert buy.status == "filled"
    assert broker.get_balance().cash_mxn == Decimal("900.00")
    assert len(broker.get_positions()) == 1
    sell = broker.place_market_sell(
        book="btc_mxn", amount_mxn=Decimal("100"), price=Decimal("60")
    )
    assert sell.status == "filled"
    assert broker.get_balance().equity_mxn > Decimal("1000")
    assert broker.get_order_status(buy.id).status == "filled"
    assert broker.cancel_order(buy.id).status == "cancelled"


def test_bitso_broker_stub_never_sends_real_orders():
    broker = BitsoBroker(live_enabled=False)
    assert broker.connect().live_enabled is False
    with pytest.raises(LiveTradingDisabledError):
        broker.place_market_buy(
            book="btc_mxn", amount_mxn=Decimal("100"), price=Decimal("50")
        )
    assert broker.get_ticker("btc_mxn")["source"] == "bitso_stub"


def test_broker_factory_defaults_to_paper_when_live_trading_false():
    class Settings:
        live_trading = False

    broker = BrokerFactory(settings=Settings()).create()
    assert isinstance(broker, PaperBroker)
    assert isinstance(BrokerFactory(settings=Settings()).create("bitso"), BitsoBroker)
    with pytest.raises(ValueError):
        BrokerFactory(settings=Settings()).create("unknown")


def test_execution_engine_translates_ai_decision_to_broker_order():
    decision = DecisionResult(
        "buy",
        80,
        Decimal("75"),
        "bull",
        DecisionExplanation(("momentum",), tuple(), tuple(), 80, "buy"),
    )
    broker = PaperBroker(initial_cash_mxn=1000)
    order = ExecutionEngine(broker=broker).execute(
        ExecutionRequest(
            decision=decision,
            book="btc_mxn",
            amount_mxn=Decimal("100"),
            price=Decimal("50"),
        )
    )
    assert order is not None
    assert order.status == "filled"
    assert broker.health().connected is True


def test_broker_reports_are_deterministic():
    health = PaperBroker().connect()
    assert "paper" in export_broker_status_json(health)
    assert "Broker Status" in export_broker_status_markdown(health)
