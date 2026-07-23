from __future__ import annotations

import warnings

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.config import Settings
from app.main import create_app

pytestmark = pytest.mark.api


def test_lifespan_stops_runtime_before_disposing_database_without_on_event_warning(
    tmp_path, fake_bitso, monkeypatch
):
    settings = Settings(
        app_env="test",
        app_password="test-password",
        session_secret="test-session-secret-with-more-than-32-characters",
        session_cookie_secure=False,
        database_url=f"sqlite:///{tmp_path / 'lifespan.db'}",
        paul_data_dir=str(tmp_path / "data"),
        runtime_auto_start=False,
        live_trading=False,
    )
    shutdown_events = []

    async def fake_shutdown_runtime(application):
        shutdown_events.append(("runtime", application))

    monkeypatch.setattr(main_module, "shutdown_runtime", fake_shutdown_runtime)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        application = create_app(settings, fake_bitso)
        assert application.router.on_shutdown == []

        engine = application.state.db_engine
        monkeypatch.setattr(
            type(engine),
            "dispose",
            lambda self: shutdown_events.append(("database", self)),
        )

        with TestClient(application) as client:
            assert client.get("/health").json() == {
                "status": "ok",
                "mode": "simulation",
            }

    assert shutdown_events == [
        ("runtime", application),
        ("database", engine),
    ]
    assert not any("on_event is deprecated" in str(item.message) for item in caught)
