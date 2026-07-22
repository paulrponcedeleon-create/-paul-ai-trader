from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit

from app.brokers.bitso import BitsoBroker, LiveTradingDisabledError
from app.brokers.factory import BrokerFactory
from app.live import (
    ExecutionAuditLog,
    LiveOrderRequest,
    LiveTradingArmState,
    LiveTradingGuard,
    OrderValidationRules,
    OrderValidator,
)
from app.live.reports import (
    export_audit_report,
    export_guard_report,
    export_live_status_report,
)


@dataclass
class SettingsStub:
    live_trading: bool = False
    bitso_api_key: str = ""
    bitso_api_secret: str = ""
    app_env: str = "test"
    max_order_mxn: float = 200.0
    live_books_set: set[str] = None

    def __post_init__(self):
        if self.live_books_set is None:
            self.live_books_set = {"btc_mxn", "eth_mxn"}


class FakeBitsoClient:
    def __init__(self) -> None:
        self.market_orders = []

    def balance(self):
        return {"payload": {"balances": [{"currency": "mxn", "available": "1000"}]}}

    def open_orders(self):
        return {"payload": []}

    def place_market_order(self, book: str, side: str, amount_mxn: float):
        self.market_orders.append((book, side, amount_mxn))
        return {
            "payload": {
                "oid": "o1",
                "book": book,
                "side": side,
                "type": "market",
                "status": "accepted",
                "minor": str(amount_mxn),
            }
        }


def test_guard_blocks_when_live_trading_false_and_audits_no_order():
    settings = SettingsStub()
    client = FakeBitsoClient()
    audit = ExecutionAuditLog()
    broker = BitsoBroker(
        live_enabled=False, settings=settings, client=client, audit_log=audit
    )
    broker.connect()

    with pytest.raises(LiveTradingDisabledError):
        broker.place_market_buy(book="btc_mxn", amount_mxn=Decimal("10"))

    assert client.market_orders == []
    assert audit.list()[0].result == "rejected"
    assert "LIVE_TRADING" in audit.list()[0].reason


def test_guard_requires_credentials_arming_confirmation_and_connected_broker():
    settings = SettingsStub(live_trading=True, bitso_api_key="k", bitso_api_secret="s")
    arm_state = LiveTradingArmState()
    broker = BitsoBroker(
        live_enabled=True,
        settings=settings,
        client=FakeBitsoClient(),
        arm_state=arm_state,
    )
    request = LiveOrderRequest("btc_mxn", "buy", "market", Decimal("10"))

    decision = LiveTradingGuard(
        settings=settings, broker=broker, arm_state=arm_state
    ).evaluate(request)
    assert decision.allowed is False
    assert "Trading real no armado." in decision.reasons

    arm_state.arm("token-123")
    broker.connect()
    decision = LiveTradingGuard(
        settings=settings, broker=broker, arm_state=arm_state
    ).evaluate(request, confirmation_token="token-123")
    assert decision.allowed is True


def test_order_validator_rejects_size_precision_symbol_and_balance():
    validator = OrderValidator(
        OrderValidationRules(
            max_amount_mxn=Decimal("50"), allowed_books=frozenset({"btc_mxn"})
        )
    )
    request = LiveOrderRequest(
        "doge_mxn", "buy", "limit", Decimal("55.001"), Decimal("0")
    )
    checks = validator.validate(request, balance_mxn=Decimal("10"))
    failed = {check.name for check in checks if not check.passed}
    assert {"book_allowed", "max_amount", "precision", "price", "balance"} <= failed


def test_authenticated_bitso_broker_mock_executes_only_when_all_guards_pass():
    settings = SettingsStub(live_trading=True, bitso_api_key="k", bitso_api_secret="s")
    client = FakeBitsoClient()
    arm = LiveTradingArmState(True, "go-live")
    audit = ExecutionAuditLog()
    broker = BitsoBroker(
        live_enabled=True,
        settings=settings,
        client=client,
        arm_state=arm,
        audit_log=audit,
    )
    broker.connect()

    order = broker.place_market_buy(book="btc_mxn", amount_mxn=Decimal("10"))

    assert order.status == "accepted"
    assert client.market_orders == [("btc_mxn", "buy", 10.0)]
    assert audit.list()[0].result == "accepted"


def test_broker_factory_still_defaults_to_paper_when_disabled():
    assert (
        BrokerFactory(settings=SettingsStub(live_trading=False)).create().name
        == "paper"
    )


def test_live_reports_are_public_and_deterministic():
    decision = LiveTradingGuard(
        settings=SettingsStub(), broker=BitsoBroker()
    ).evaluate()
    assert "LIVE_TRADING" in str(export_guard_report(decision))
    assert "live_trading" in export_live_status_report({"live_trading": False})
    assert export_audit_report([]) == {"items": [], "total": 0, "rejections": 0}
