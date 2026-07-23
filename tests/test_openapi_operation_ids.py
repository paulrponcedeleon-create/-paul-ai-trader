from __future__ import annotations

import warnings

import pytest

from app.config import Settings
from app.main import create_app

pytestmark = pytest.mark.api


def test_openapi_operation_ids_are_unique(tmp_path, fake_bitso):
    settings = Settings(
        app_env="test",
        app_password="test-password",
        session_secret="test-session-secret-with-more-than-32-characters",
        session_cookie_secure=False,
        database_url=f"sqlite:///{tmp_path / 'openapi.db'}",
        paul_data_dir=str(tmp_path / "data"),
        runtime_auto_start=False,
        live_trading=False,
    )
    application = create_app(settings, fake_bitso)

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
