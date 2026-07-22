from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api


def test_research_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/research/start" in paths
    assert "/research/status" in paths
    assert "/research/results" in paths
    assert "/research/report" in paths
