import asyncio
from types import SimpleNamespace

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


def test_main_lifespan_calls_startup_before_serving():
    source = open("app/main.py", encoding="utf-8").read()

    assert "await startup_runtime(application)" in source
    assert source.index("await startup_runtime(application)") < source.index("yield")
