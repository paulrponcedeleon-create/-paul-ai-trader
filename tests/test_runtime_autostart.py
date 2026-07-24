import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main_module
from app.api.routes.runtime import shutdown_runtime, startup_runtime


def test_test_environment_initializes_multiuser_runtime_controller_without_tasks():
    application = SimpleNamespace(
        state=SimpleNamespace(
            settings=SimpleNamespace(
                app_env="test",
                runtime_auto_start=True,
                live_trading=False,
                runtime_broker="paper",
            )
        )
    )

    asyncio.run(startup_runtime(application))

    assert callable(application.state.user_runtime_controller)
    assert application.state.runtime_engines == {}
    assert application.state.runtime_background_tasks == {}
    asyncio.run(shutdown_runtime(application))


def test_user_can_disable_only_their_own_runtime(client):
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200

    account = client.patch(
        "/api/account/preferences",
        json={"bot_enabled": False},
    )
    status = client.get("/runtime/status")

    assert account.status_code == 200
    assert account.json()["bot_enabled"] is False
    assert status.status_code == 200
    assert status.json()["automatic"] is False
    assert status.json()["startup_state"] == "disabled_by_user"
    assert status.json()["background_task_active"] is False


def test_runtime_routes_require_a_user_session(client):
    assert client.get("/runtime/status").status_code == 401
    assert client.post("/runtime/start").status_code == 401
    assert client.post("/runtime/stop").status_code == 401


def test_main_lifespan_serves_health_while_runtime_is_still_starting(tmp_path, monkeypatch):
    blocker = asyncio.Event()

    async def slow_startup(application):
        await blocker.wait()

    monkeypatch.setattr(main_module, "startup_runtime", slow_startup)
    settings = main_module.Settings(
        app_env="test",
        app_password="test-password",
        session_secret="test-session-secret-with-at-least-32-characters",
        session_cookie_secure=False,
        database_url=f"sqlite:///{tmp_path / 'nonblocking.db'}",
        paul_data_dir=str(tmp_path),
    )
    application = main_module.create_app(settings)

    with TestClient(application) as client:
        response = client.get("/health")
        task = application.state.runtime_bootstrap_task

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "mode": "simulation"}
        assert task is not None
        assert task.done() is False


def test_main_lifespan_schedules_runtime_before_serving():
    source = open("app/main.py", encoding="utf-8").read()

    assert "asyncio.create_task(" in source
    assert "_bootstrap_runtime_without_blocking(application)" in source
    assert source.index("asyncio.create_task(") < source.index("yield")
    assert "await startup_runtime(application)" not in source.split("async def lifespan", 1)[1].split("application = FastAPI", 1)[0]
