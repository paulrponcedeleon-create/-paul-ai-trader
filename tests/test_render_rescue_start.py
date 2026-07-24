from __future__ import annotations

import subprocess

from scripts import render_start


def test_failed_migration_still_starts_web_in_rescue_mode(monkeypatch):
    captured = {}

    def fail_migration(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    def capture_exec(executable, command, environment):
        captured["executable"] = executable
        captured["command"] = command
        captured["environment"] = environment

    monkeypatch.setattr(render_start.subprocess, "run", fail_migration)
    monkeypatch.setattr(render_start.os, "execvpe", capture_exec)
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("RUNTIME_AUTO_START", "true")

    render_start.main()

    assert captured["command"][-1] == "10000"
    assert captured["environment"]["RENDER_MIGRATION_STATUS"] == "failed"
    assert captured["environment"]["RUNTIME_AUTO_START"] == "false"


def test_successful_migration_keeps_configured_runtime_setting(monkeypatch):
    captured = {}

    monkeypatch.setattr(render_start.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        render_start.os,
        "execvpe",
        lambda executable, command, environment: captured.update(
            {"command": command, "environment": environment}
        ),
    )
    monkeypatch.setenv("PORT", "10001")
    monkeypatch.setenv("RUNTIME_AUTO_START", "false")

    render_start.main()

    assert captured["command"][-1] == "10001"
    assert captured["environment"]["RENDER_MIGRATION_STATUS"] == "ok"
    assert captured["environment"]["RUNTIME_AUTO_START"] == "false"
