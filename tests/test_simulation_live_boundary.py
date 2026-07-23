from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.brokers.bitso import BitsoBroker
from app.config import Settings
from app.live import LiveTradingArmState
from app.main import create_app
from app.runtime import RuntimeConfig, RuntimeEngine


class _SyncBitsoOrderSpy:
    def __init__(self) -> None:
        self.market_orders: list[tuple[str, str, float]] = []

    def balance(self):
        return {
            "payload": {
                "balances": [
                    {
                        "currency": "mxn",
                        "available": "5000",
                        "total": "5000",
                    }
                ]
            }
        }

    def open_orders(self):
        return {"payload": []}

    def place_market_order(self, book: str, side: str, amount_mxn: float):
        self.market_orders.append((book, side, amount_mxn))
        return {
            "payload": {
                "oid": "forbidden-live-order",
                "book": book,
                "side": side,
                "type": "market",
                "status": "accepted",
                "minor": str(amount_mxn),
            }
        }


@dataclass(frozen=True)
class _Candle:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class _ProviderStatus:
    def to_public_dict(self):
        return {"connected": True, "provider": "simulation-test"}


class _DeterministicMarketData:
    def __init__(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.rows = [
            _Candle(
                timestamp=start + timedelta(minutes=index),
                open=Decimal(str(100 + index)),
                high=Decimal(str(102 + index)),
                low=Decimal(str(99 + index)),
                close=Decimal(str(101 + index)),
                volume=Decimal("10"),
            )
            for index in range(30)
        ]
        self.connected = False

    async def connect(self):
        self.connected = True
        return self.status()

    async def disconnect(self):
        self.connected = False
        return self.status()

    async def get_candles(self, _book: str, _timeframe: str, limit: int = 100):
        return self.rows[-limit:]

    def status(self):
        return _ProviderStatus()


class _ForcedBuyDecision:
    action = "buy"

    def to_public_dict(self):
        return {
            "action": "buy",
            "score": 100,
            "confidence": 100,
            "reason": "Compra forzada para validar la frontera de seguridad.",
        }


class _ForcedBuyAI:
    def evaluate(self, _request):
        return _ForcedBuyDecision()


class _Strategy:
    def generate_signal(self, _rows):
        return SimpleNamespace(
            action="buy",
            confidence=100,
            reason="Señal forzada de prueba.",
            reference_price=100.0,
        )


class _StrategyFactory:
    def create(self, *_args, **_kwargs):
        return _Strategy()


def _simulation_settings(tmp_path, **overrides) -> Settings:
    values = {
        "_env_file": None,
        "app_env": "test",
        "app_password": "test-password",
        "session_secret": "test-session-secret-with-more-than-32-characters",
        "session_cookie_secure": False,
        "database_url": f"sqlite:///{tmp_path / 'simulation-boundary.db'}",
        "paul_data_dir": str(tmp_path / "data"),
        "live_trading": False,
        "bitso_api_key": "configured-read-only-key",
        "bitso_api_secret": "configured-read-only-secret",
        "runtime_auto_start": False,
        "runtime_broker": "paper",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.unit
def test_configuration_rejects_bitso_runtime_when_live_trading_is_false(tmp_path):
    with pytest.raises(ValueError, match="RUNTIME_BROKER debe permanecer en paper"):
        _simulation_settings(tmp_path, runtime_broker="bitso")


@pytest.mark.api
def test_simulation_endpoints_never_submit_a_bitso_order(tmp_path, fake_bitso):
    settings = _simulation_settings(tmp_path)
    application = create_app(settings, fake_bitso)

    with TestClient(application) as client:
        login = client.post("/api/login", json={"password": settings.app_password})
        assert login.status_code == 200

        broker_status = client.get("/broker/status")
        assert broker_status.status_code == 200
        assert broker_status.json()["broker"] == "paper"

        armed = client.post("/live/arm", params={"token": "simulation-lock"})
        assert armed.status_code == 200
        assert armed.json()["armed"] is True

        validation = client.post(
            "/live/validate",
            json={
                "book": "btc_mxn",
                "side": "buy",
                "order_type": "market",
                "amount_mxn": 100,
                "confirmation_token": "simulation-lock",
            },
        )
        assert validation.status_code == 200
        validation_payload = validation.json()
        assert validation_payload["allowed"] is False
        assert any("LIVE_TRADING" in reason for reason in validation_payload["reasons"])

        simulated = client.post(
            "/api/orders",
            json={
                "book": "btc_mxn",
                "side": "buy",
                "amount_mxn": 100,
                "daily_pnl_mxn": 0,
                "open_orders": 0,
            },
        )
        assert simulated.status_code == 200, simulated.text
        assert simulated.json()["status"] == "simulated"

    assert fake_bitso.place_order_calls == 0


@pytest.mark.integration
def test_forced_runtime_buy_cannot_reach_bitso_when_live_trading_is_false(tmp_path):
    settings = _simulation_settings(tmp_path)
    client = _SyncBitsoOrderSpy()
    arm_state = LiveTradingArmState(armed=True, token="simulation-lock")
    disabled_bitso = BitsoBroker(
        live_enabled=False,
        settings=settings,
        client=client,
        arm_state=arm_state,
    )
    runtime = RuntimeEngine(
        config=RuntimeConfig(
            books=("btc_mxn",),
            broker_name="bitso",
            market_data_provider="simulation-test",
            min_trade_amount_mxn=Decimal("10"),
            max_trade_amount_mxn=Decimal("100"),
            capital_reserve_pct=Decimal("20"),
        ),
        market_data=_DeterministicMarketData(),
        strategy_factory=_StrategyFactory(),
        ai_engine=_ForcedBuyAI(),
        broker=disabled_bitso,
        settings=settings,
    )

    async def scenario():
        await runtime.start()
        result = await runtime.run_once()
        await runtime.stop()
        return result

    result = asyncio.run(scenario())

    assert result.cycles == 1
    assert result.last_decision is not None
    assert result.last_decision["action"] == "buy"
    assert result.last_error is not None
    assert "LiveTradingDisabledError" in result.last_error
    assert client.market_orders == []
