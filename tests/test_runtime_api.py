from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api


def test_runtime_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/runtime/start" in paths
    assert "/runtime/stop" in paths
    assert "/runtime/status" in paths
    assert "/runtime/components" in paths
    assert "/runtime/config" in paths
