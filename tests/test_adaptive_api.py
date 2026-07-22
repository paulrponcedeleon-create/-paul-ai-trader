from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api


def test_adaptive_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/adaptive/status" in paths
    assert "/adaptive/selection" in paths
    assert "/adaptive/portfolio" in paths
    assert "/adaptive/report" in paths
