from __future__ import annotations

from collections import Counter
import warnings

import pytest

from app.config import Settings
from app.main import create_app

pytestmark = pytest.mark.api


def _settings(tmp_path) -> Settings:
    return Settings(
        app_env="test",
        app_password="test-password",
        session_secret="test-session-secret-with-more-than-32-characters",
        session_cookie_secure=False,
        database_url=f"sqlite:///{tmp_path / 'openapi.db'}",
        paul_data_dir=str(tmp_path / "data"),
        runtime_auto_start=False,
        live_trading=False,
    )


def test_openapi_operation_ids_are_unique(tmp_path, fake_bitso):
    application = create_app(_settings(tmp_path), fake_bitso)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        schema = application.openapi()

    duplicate_warnings = [
        str(item.message)
        for item in caught
        if "Duplicate Operation ID" in str(item.message)
    ]
    assert duplicate_warnings == []

    operation_ids = [
        operation["operationId"]
        for path_item in schema["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    assert len(operation_ids) == len(set(operation_ids))


def test_market_compatibility_routes_have_one_router_owner(tmp_path, fake_bitso):
    application = create_app(_settings(tmp_path), fake_bitso)
    expected = {
        ("/api/market/{book}", "GET"),
        ("/api/positions", "GET"),
        ("/api/simulations/{simulation_id}/close", "POST"),
        ("/api/orders", "POST"),
    }

    registrations = [
        (route.path, method, route.endpoint.__module__)
        for route in application.routes
        for method in getattr(route, "methods", set())
        if (route.path, method) in expected
    ]
    counts = Counter((path, method) for path, method, _ in registrations)

    assert counts == Counter({route_key: 1 for route_key in expected})
    assert all(
        owner == "app.api.routes.markets" for _, _, owner in registrations
    )
