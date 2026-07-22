from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api


def test_ai_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/ai/evaluate" in paths
    assert "/ai/decision" in paths
    assert "/ai/explanation" in paths
    assert "/ai/confidence" in paths
