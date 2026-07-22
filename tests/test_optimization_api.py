from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

pytestmark = pytest.mark.api


def test_optimization_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/optimization/grid" in paths
    assert "/optimization/random" in paths
    assert "/optimization" in paths
