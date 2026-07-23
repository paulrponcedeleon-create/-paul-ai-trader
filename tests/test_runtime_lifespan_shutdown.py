from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

from app.api.routes.runtime import shutdown_runtime

pytestmark = pytest.mark.api


class _RuntimeProbe:
    def __init__(self):
        self.running = True
        self.stop_calls = 0

    async def stop(self):
        self.stop_calls += 1
        self.running = False


def test_shutdown_runtime_cancels_background_task_and_disconnects_once():
    async def scenario():
        runtime = _RuntimeProbe()
        application = SimpleNamespace(
            state=SimpleNamespace(runtime_engine=runtime)
        )
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def background():
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        task = asyncio.create_task(background(), name="runtime-lifespan-test")
        application.state.runtime_background_task = task
        await started.wait()

        await shutdown_runtime(application)
        await shutdown_runtime(application)
        return application, runtime, task, cancelled.is_set()

    application, runtime, task, cancelled = asyncio.run(scenario())

    assert runtime.stop_calls == 1
    assert runtime.running is False
    assert cancelled is True
    assert task.cancelled() is True
    assert application.state.runtime_background_task is None


def test_shutdown_runtime_does_not_create_an_unused_engine():
    application = SimpleNamespace(state=SimpleNamespace())

    asyncio.run(shutdown_runtime(application))

    assert application.state.runtime_background_task is None
    assert not hasattr(application.state, "runtime_engine")
