from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api


def test_live_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/live/status" in paths
    assert "/live/guards" in paths
    assert "/live/arm" in paths
    assert "/live/disarm" in paths
    assert "/live/validate" in paths
    assert "/live/audit" in paths
