import asyncio
from types import SimpleNamespace

from app.api.routes.runtime import shutdown_runtime, startup_runtime


class FakeRuntime:
    def __init__(self, *, fail_start: bool = False):
        self.running = False
        self.start_calls = 0
        self.stop_calls = 0
        self.run_calls = 0
        self.fail_start = fail_start
        self.config = SimpleNamespace(loop_interval_seconds=60.0)

    async def start(self):
        self.start_calls += 1
        if self.fail_start:
            raise RuntimeError("startup failed")
        self.running = True
        return SimpleNamespace()

    async def stop(self):
        self.stop_calls += 1
        self.running = False
        return SimpleNamespace()

    async def run_once(self):
        self.run_calls += 1
        await asyncio.sleep(0)


def make_application(*, runtime, auto_start=True, app_env="development", live=False, broker="paper"):
    settings = SimpleNamespace(
        runtime_auto_start=auto_start,
        app_env=app_env,
        live_trading=live,
        runtime_broker=broker,
    )
    return SimpleNamespace(
        state=SimpleNamespace(settings=settings, runtime_engine=runtime)
    )


def test_lifecycle_starts_paper_runtime_and_background_loop_once():
    runtime = FakeRuntime()
    application = make_application(runtime=runtime)

    async def scenario():
        await startup_runtime(application)
        await asyncio.sleep(0)
        assert runtime.running is True
        assert runtime.start_calls == 1
        assert runtime.run_calls >= 1
        assert application.state.runtime_startup_state == "automatic_running"
        assert application.state.runtime_startup_error is None
        assert application.state.runtime_background_task.done() is False

        await startup_runtime(application)
        assert runtime.start_calls == 1

        await shutdown_runtime(application)
        assert runtime.running is False
        assert runtime.stop_calls == 1
        assert application.state.runtime_background_task is None

    asyncio.run(scenario())


def test_lifecycle_does_not_start_in_test_or_live_mode():
    async def scenario():
        test_runtime = FakeRuntime()
        test_application = make_application(runtime=test_runtime, app_env="test")
        await startup_runtime(test_application)
        assert test_runtime.start_calls == 0
        assert test_application.state.runtime_startup_state == "test_disabled"

        live_runtime = FakeRuntime()
        live_application = make_application(runtime=live_runtime, live=True)
        await startup_runtime(live_application)
        assert live_runtime.start_calls == 0
        assert live_application.state.runtime_startup_state == "blocked_live_mode"

        disabled_runtime = FakeRuntime()
        disabled_application = make_application(runtime=disabled_runtime, auto_start=False)
        await startup_runtime(disabled_application)
        assert disabled_runtime.start_calls == 0
        assert disabled_application.state.runtime_startup_state == "disabled"

    asyncio.run(scenario())


def test_startup_failure_is_visible_without_crashing_application():
    runtime = FakeRuntime(fail_start=True)
    application = make_application(runtime=runtime)

    asyncio.run(startup_runtime(application))

    assert runtime.start_calls == 1
    assert runtime.running is False
    assert application.state.runtime_startup_state == "error"
    assert application.state.runtime_startup_error == "RuntimeError: startup failed"
    assert getattr(application.state, "runtime_background_task", None) is None


def test_main_lifespan_calls_startup_before_serving():
    source = open("app/main.py", encoding="utf-8").read()

    assert "await startup_runtime(application)" in source
    assert source.index("await startup_runtime(application)") < source.index("yield")
