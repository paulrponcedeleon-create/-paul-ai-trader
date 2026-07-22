from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api


def test_system_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/system/health" in paths
    assert "/system/status" in paths
    assert "/system/watchdog" in paths
    assert "/system/circuit-breakers" in paths
    assert "/system/recovery" in paths
    assert "/system/metrics" in paths
    assert "/system/snapshot" in paths
    assert "/system/restore" in paths
