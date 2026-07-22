from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

pytestmark = pytest.mark.api


def test_paper_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/paper/start" in paths
    assert "/paper/status" in paths
    assert "/paper/portfolio" in paths
