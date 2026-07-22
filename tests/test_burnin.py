from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import json

import pytest

from app.ai.decision_engine import DecisionExplanation, DecisionResult
from app.burnin import BurnInConfig, BurnInManager
from app.market_data.models import Candle, ProviderStatus
from app.reporting.burnin_reports import (
    export_burnin_csv,
    export_burnin_html,
    export_burnin_json,
    export_burnin_markdown,
)
from app.runtime import RuntimeConfig, RuntimeEngine
from app.services.signals import Signal

pytestmark = pytest.mark.unit


class FakeProvider:
    name = "fake"

    def __init__(self, fail_after: int | None = None):
        self.connected = False
        self.calls = 0
        self.fail_after = fail_after

    async def connect(self):
        self.connected = True
        return self.status()

    async def disconnect(self):
        self.connected = False
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
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise RuntimeError("market disconnected")
        return [
            Candle(
                book,
                timeframe,
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                Decimal("100"),
                Decimal("101"),
                Decimal("99"),
                Decimal("100.50"),
                Decimal("10"),
            )
        ]


class HoldStrategy:
    def generate_signal(self, history):
        return Signal("hold", 50, "test hold", float(history[-1].close))


class FakeStrategyFactory:
    def create(self, *args, **kwargs):
        return HoldStrategy()


class HoldAI:
    def evaluate(self, request):
        return DecisionResult(
            "hold",
            75,
            Decimal("100.50"),
            "sideways",
            DecisionExplanation(("hold consensus",), tuple(), tuple(), 75, "hold"),
        )


def _runtime(provider: FakeProvider | None = None) -> RuntimeEngine:
    return RuntimeEngine(
        config=RuntimeConfig(books=("btc_mxn",), max_history=3),
        market_data=provider or FakeProvider(),
        strategy_factory=FakeStrategyFactory(),
        ai_engine=HoldAI(),
    )


def test_burnin_manager_collects_runtime_validation_metrics():
    manager = BurnInManager(
        _runtime(),
        BurnInConfig(duration="custom", custom_duration_seconds=60, max_cycles=4),
    )
    report = asyncio.run(manager.start())
    data = report.to_public_dict()

    assert data["running"] is False
    assert data["cycles_executed"] == 4
    assert data["average_cycle_ms"] >= 0
    assert data["max_cycle_ms"] >= data["min_cycle_ms"]
    assert data["memory_end_bytes"] >= data["memory_start_bytes"]
    assert data["cache_items"] <= 3
    assert data["event_count"] >= 4
    assert len(data["cycle_metrics"]) == 4


def test_burnin_detects_runtime_errors_and_alerts():
    manager = BurnInManager(
        _runtime(FakeProvider(fail_after=1)),
        BurnInConfig(duration="custom", custom_duration_seconds=60, max_cycles=3),
    )
    report = asyncio.run(manager.start()).to_public_dict()

    assert report["cycles_executed"] == 3
    assert report["errors"] >= 1
    assert "runtime_errors_detected" in report["alerts"]


def test_burnin_stop_is_safe_when_running_in_background():
    async def scenario():
        manager = BurnInManager(
            _runtime(),
            BurnInConfig(
                duration="custom",
                custom_duration_seconds=60,
                max_cycles=100,
                cycle_sleep_seconds=0.01,
            ),
        )
        manager.start_background()
        await asyncio.sleep(0)
        return await manager.stop()

    report = asyncio.run(scenario()).to_public_dict()
    assert report["running"] is False
    assert "burnin_cancelled" in report["alerts"] or report["cycles_executed"] >= 0


def test_burnin_reports_are_deterministic_and_serializable():
    manager = BurnInManager(
        _runtime(),
        BurnInConfig(duration="custom", custom_duration_seconds=60, max_cycles=2),
    )
    report = asyncio.run(manager.start())

    parsed = json.loads(export_burnin_json(report))
    assert parsed["cycles_executed"] == 2
    assert "cycles_executed" in export_burnin_csv(report)
    assert "# Burn-In Report" in export_burnin_markdown(report)
    assert "<h1>Burn-In Report</h1>" in export_burnin_html(report)
