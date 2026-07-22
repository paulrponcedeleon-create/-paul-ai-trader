from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api


def test_analytics_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/analytics/summary" in paths
    assert "/analytics/equity" in paths
    assert "/analytics/snapshot" in paths
