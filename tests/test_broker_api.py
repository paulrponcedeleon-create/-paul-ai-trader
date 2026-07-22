from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api


def test_broker_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/broker/status" in paths
    assert "/broker/health" in paths
    assert "/broker/connect" in paths
    assert "/broker/disconnect" in paths
