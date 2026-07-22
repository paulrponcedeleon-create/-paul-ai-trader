from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api


def test_validation_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/validation/status" in paths
    assert "/validation/promotions" in paths
    assert "/validation/retirements" in paths
    assert "/validation/report" in paths
