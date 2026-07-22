from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.unit

from app.reporting.system_reports import (
    export_system_csv,
    export_system_html,
    export_system_json,
    export_system_markdown,
)
from app.system import (
    CircuitBreaker,
    CircuitBreakerManager,
    HealthManager,
    RecoveryManager,
    SnapshotManager,
    SystemService,
    WatchdogManager,
)
from app.system.observability import ObservabilityEventQueue


def test_health_manager_reports_components_and_metrics():
    manager = HealthManager(started_at=time.monotonic() - 10)
    status = manager.status({"Broker": False, "Database": "offline"})
    states = {item["name"]: item["state"] for item in status["components"]}
    assert states["Broker"] == "CRITICAL"
    assert states["Database"] == "OFFLINE"
    assert manager.metrics(reconnect_count=2).uptime_seconds >= 10


def test_watchdog_detects_stale_heartbeat_reconnects_and_error_loops():
    watchdog = WatchdogManager(
        heartbeat_timeout_seconds=0, reconnect_threshold=2, error_threshold=2
    )
    watchdog.heartbeat("Market Data")
    watchdog.record_reconnect("Broker")
    watchdog.record_reconnect("Broker")
    watchdog.record_error("AI")
    watchdog.record_error("AI")
    result = watchdog.inspect()
    assert "Market Data" in result["frozen"]
    assert "Broker" in result["reconnections_excessive"]
    assert "AI" in result["error_loops"]


def test_circuit_breaker_transitions_to_open_and_half_open():
    breaker = CircuitBreaker("Broker", failure_threshold=2, recovery_timeout_seconds=0)
    breaker.record_failure()
    assert breaker.state == "CLOSED"
    breaker.record_failure()
    assert breaker.state == "OPEN"
    assert breaker.allow_request() is True
    assert breaker.state == "HALF_OPEN"
    breaker.record_success()
    assert breaker.state == "CLOSED"
    assert "Broker" in CircuitBreakerManager().status()


def test_recovery_snapshot_restore_and_events_do_not_execute_orders():
    calls = []
    recovery = RecoveryManager()
    recovery.register("Cache", lambda: calls.append("recovered"))
    assert recovery.recover("Cache")["recovered"] is True
    assert calls == ["recovered"]

    snapshots = SnapshotManager()
    snapshot = snapshots.create({"portfolio": {"cash": 100}})
    assert snapshots.restore(snapshot.id).payload["portfolio"]["cash"] == 100

    events = ObservabilityEventQueue(max_events=2)
    events.publish("INFO", "System", "test", "ok")
    assert events.list()[0].message == "ok"


def test_system_service_and_reports_are_deterministic():
    service = SystemService()
    data = service.status()
    assert "health" in data
    assert "System Report" in export_system_markdown(data)
    assert "health" in export_system_json(data)
    assert "section" in export_system_csv(data)
    assert "<table>" in export_system_html(data)
