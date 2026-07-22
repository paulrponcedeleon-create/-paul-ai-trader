from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api


def test_experiment_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/experiments" in paths
    assert "/experiments/run" in paths
    assert "/experiments/compare" in paths
    assert "/experiments/report" in paths
    assert "/experiments/{experiment_id}" in paths
