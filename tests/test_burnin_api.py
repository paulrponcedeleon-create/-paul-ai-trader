from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api


def test_burnin_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/burnin/start" in paths
    assert "/burnin/stop" in paths
    assert "/burnin/status" in paths
    assert "/burnin/report" in paths
