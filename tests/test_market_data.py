from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.unit

from app.market_data import (
    MarketDataCache,
    MockMarketDataProvider,
    ProviderFactory,
    WebSocketController,
)
from app.reporting.market_data_reports import (
    export_market_data_status_json,
    export_market_data_status_markdown,
    market_data_quality_report,
)


def test_mock_provider_cache_events_and_read_only_data():
    async def scenario():
        cache = MarketDataCache(max_events=10)
        provider = MockMarketDataProvider(cache)
        await provider.connect()
        ticker = await provider.get_ticker("btc_mxn")
        candles = await provider.get_candles("btc_mxn", "1m", 3)
        orderbook = await provider.get_orderbook("btc_mxn")
        trades = await provider.get_recent_trades("btc_mxn", 2)

        assert provider.status().read_only is True
        assert provider.status().live_trading_enabled is False
        assert ticker.spread > 0
        assert candles == cache.latest_candles("btc_mxn", "1m", 3)
        assert orderbook.spread > 0
        assert len(trades) == 2
        assert {event.event_type for event in cache.events} >= {
            "reconnect",
            "ticker_updated",
            "candle_closed",
            "orderbook_updated",
        }

    asyncio.run(scenario())


def test_websocket_controller_heartbeat_reconnect_and_resubscribe():
    async def scenario():
        provider = MockMarketDataProvider()
        ws = WebSocketController(
            provider, backoff_initial_seconds=1, backoff_max_seconds=4
        )
        await ws.connect()
        await ws.subscribe("btc_mxn", ("ticker", "orderbook"))
        await provider.disconnect()
        status = await ws.heartbeat()
        reconnect_status = await ws.reconnect()

        assert status.connected is True
        assert reconnect_status.reconnects >= 1
        assert "btc_mxn:ticker" in reconnect_status.subscriptions
        assert ws.backoff_seconds == 2

    asyncio.run(scenario())


def test_provider_factory_and_reports_are_deterministic():
    factory = ProviderFactory()
    provider = factory.create("mock")
    status = provider.status().to_public_dict()
    report = market_data_quality_report(status=status, latency_ms=None, events=[])

    assert provider.name == "mock"
    assert report["quality"] == "ok"
    assert "mock" in export_market_data_status_json(status)
    assert "Live Market Data Status" in export_market_data_status_markdown(status)


def test_provider_factory_rejects_unknown_provider():
    with pytest.raises(ValueError):
        ProviderFactory().create("unknown")
