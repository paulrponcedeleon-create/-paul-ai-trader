from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from starlette.requests import Request

pytest.importorskip("fastapi")

from app.api.routes import runtime as runtime_routes

pytestmark = pytest.mark.api


class _StatusSnapshot:
    def to_public_dict(self):
        return {"running": False, "history_points": 0}


class _RuntimeProbe:
    def __init__(self):
        self.config = SimpleNamespace(
            market_data_provider="bitso",
            broker_name="paper",
        )
        self.status_calls = 0
        self.start_calls = 0

    def status(self):
        self.status_calls += 1
        return _StatusSnapshot()

    async def start(self):
        self.start_calls += 1
        raise AssertionError("GET /runtime/status must never start the Runtime")


def test_runtime_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/runtime/start" in paths
    assert "/runtime/stop" in paths
    assert "/runtime/status" in paths
    assert "/runtime/components" in paths
    assert "/runtime/config" in paths


def test_runtime_status_is_read_only_even_when_auto_start_is_enabled(monkeypatch):
    runtime = _RuntimeProbe()
    app = SimpleNamespace(
        state=SimpleNamespace(
            settings=SimpleNamespace(runtime_auto_start=True, live_trading=False),
            runtime_engine=runtime,
        )
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/runtime/status",
            "headers": [],
            "query_string": b"",
            "app": app,
        }
    )

    def fail_if_background_start_is_requested(*_args, **_kwargs):
        pytest.fail("GET /runtime/status requested a background Runtime start")

    monkeypatch.setattr(
        runtime_routes,
        "_ensure_background_loop",
        fail_if_background_start_is_requested,
    )

    payload = asyncio.run(runtime_routes.runtime_status(request))

    assert payload["running"] is False
    assert payload["automatic"] is True
    assert payload["provider_label"] == "Bitso, solo lectura"
    assert payload["broker_label"] == "Dinero simulado"
    assert runtime.status_calls == 1
    assert runtime.start_calls == 0
    assert not hasattr(app.state, "runtime_background_task")
