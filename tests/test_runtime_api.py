from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from starlette.requests import Request

pytest.importorskip("fastapi")

from app.api.routes import runtime as runtime_routes

pytestmark = pytest.mark.api


class _StatusSnapshot:
    def __init__(self, running: bool = False):
        self.running = running

    def to_public_dict(self):
        return {"running": self.running, "history_points": 0}


class _RuntimeProbe:
    def __init__(self):
        self.config = SimpleNamespace(
            market_data_provider="bitso",
            broker_name="paper",
            loop_interval_seconds=5.0,
        )
        self.running = False
        self.status_calls = 0
        self.start_calls = 0
        self.stop_calls = 0
        self.run_once_calls = 0

    def status(self):
        self.status_calls += 1
        return _StatusSnapshot(self.running)

    async def start(self):
        self.start_calls += 1
        self.running = True
        return _StatusSnapshot(True)

    async def stop(self):
        self.stop_calls += 1
        self.running = False
        return _StatusSnapshot(False)

    async def run_once(self):
        self.run_once_calls += 1


def _request(runtime: _RuntimeProbe, *, auto_start: bool = True) -> Request:
    app = SimpleNamespace(
        state=SimpleNamespace(
            settings=SimpleNamespace(
                runtime_auto_start=auto_start,
                live_trading=False,
            ),
            runtime_engine=runtime,
        )
    )
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/runtime/status",
            "headers": [],
            "query_string": b"",
            "app": app,
        }
    )


def test_runtime_routes_registered(client):
    paths = set(client.app.openapi()["paths"])
    assert "/runtime/start" in paths
    assert "/runtime/stop" in paths
    assert "/runtime/status" in paths
    assert "/runtime/components" in paths
    assert "/runtime/config" in paths


def test_runtime_status_is_read_only_even_when_auto_start_is_enabled(monkeypatch):
    runtime = _RuntimeProbe()
    request = _request(runtime, auto_start=True)

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
    assert not hasattr(request.app.state, "runtime_background_task")


def test_runtime_start_is_idempotent_and_requests_one_background_loop(monkeypatch):
    runtime = _RuntimeProbe()
    request = _request(runtime, auto_start=True)
    background_requests = []

    monkeypatch.setattr(
        runtime_routes,
        "_ensure_background_loop",
        lambda received_request, received_runtime: background_requests.append(
            (received_request, received_runtime)
        ),
    )

    first = asyncio.run(runtime_routes.runtime_start(request))
    second = asyncio.run(runtime_routes.runtime_start(request))

    assert first["running"] is True
    assert second["running"] is True
    assert runtime.start_calls == 1
    assert runtime.status_calls == 1
    assert background_requests == [(request, runtime), (request, runtime)]


def test_background_loop_does_not_start_runtime_again():
    class StopLoop(Exception):
        pass

    runtime = _RuntimeProbe()
    runtime.running = True

    async def stop_after_first_cycle():
        runtime.run_once_calls += 1
        raise StopLoop

    runtime.run_once = stop_after_first_cycle

    with pytest.raises(StopLoop):
        asyncio.run(runtime_routes._background_loop(runtime))

    assert runtime.start_calls == 0
    assert runtime.run_once_calls == 1


def test_runtime_stop_is_idempotent_and_cancels_background_task():
    async def scenario():
        runtime = _RuntimeProbe()
        runtime.running = True
        request = _request(runtime, auto_start=True)
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def background():
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        task = asyncio.create_task(background(), name="runtime-stop-test")
        request.app.state.runtime_background_task = task
        await started.wait()

        first = await runtime_routes.runtime_stop(request)
        second = await runtime_routes.runtime_stop(request)
        return runtime, request, task, cancelled.is_set(), first, second

    runtime, request, task, cancelled, first, second = asyncio.run(scenario())

    assert first["running"] is False
    assert second["running"] is False
    assert runtime.stop_calls == 1
    assert runtime.status_calls == 1
    assert cancelled is True
    assert task.cancelled() is True
    assert request.app.state.runtime_background_task is None


def test_runtime_stop_still_disconnects_after_background_task_failure():
    async def scenario():
        runtime = _RuntimeProbe()
        runtime.running = True
        request = _request(runtime, auto_start=True)

        async def failed_background():
            raise RuntimeError("background failed")

        task = asyncio.create_task(failed_background())
        await asyncio.sleep(0)
        request.app.state.runtime_background_task = task

        payload = await runtime_routes.runtime_stop(request)
        return runtime, request, task, payload

    runtime, request, task, payload = asyncio.run(scenario())

    assert task.done() is True
    assert payload["running"] is False
    assert runtime.stop_calls == 1
    assert request.app.state.runtime_background_task is None
