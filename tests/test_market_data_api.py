from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api


def test_market_data_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/market/live/status" in paths
    assert "/market/live/ticker" in paths
    assert "/market/live/orderbook" in paths
    assert "/market/live/candles" in paths
    assert "/market/live/trades" in paths
    assert "/market/live/provider" in paths
