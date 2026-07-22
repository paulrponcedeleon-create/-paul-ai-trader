from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import resource
import time
from typing import Any, Literal

from app.runtime import RuntimeEngine

BurnInDuration = Literal["1h", "6h", "12h", "24h", "72h", "custom"]


@dataclass(frozen=True)
class BurnInConfig:
    duration: BurnInDuration = "1h"
    custom_duration_seconds: float | None = None
    max_cycles: int | None = None
    cycle_sleep_seconds: float = 0.0
    memory_growth_alert_bytes: int = 25 * 1024 * 1024
    max_events: int = 1000

    @property
    def duration_seconds(self) -> float:
        durations = {
            "1h": 3600.0,
            "6h": 21600.0,
            "12h": 43200.0,
            "24h": 86400.0,
            "72h": 259200.0,
        }
        if self.duration == "custom":
            return max(float(self.custom_duration_seconds or 0), 0.0)
        return durations[self.duration]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "duration": self.duration,
            "duration_seconds": self.duration_seconds,
            "custom_duration_seconds": self.custom_duration_seconds,
            "max_cycles": self.max_cycles,
            "cycle_sleep_seconds": self.cycle_sleep_seconds,
            "memory_growth_alert_bytes": self.memory_growth_alert_bytes,
            "max_events": self.max_events,
        }


@dataclass(frozen=True)
class BurnInCycleMetric:
    cycle: int
    timestamp: datetime
    runtime_ms: float
    cpu_seconds: float
    memory_bytes: int
    cache_items: int
    queue_items: int
    event_count: int
    snapshot_count: int
    errors: int
    reconnects: int

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "timestamp": self.timestamp.isoformat(),
            "runtime_ms": _finite(self.runtime_ms),
            "cpu_seconds": _finite(self.cpu_seconds),
            "memory_bytes": self.memory_bytes,
            "cache_items": self.cache_items,
            "queue_items": self.queue_items,
            "event_count": self.event_count,
            "snapshot_count": self.snapshot_count,
            "errors": self.errors,
            "reconnects": self.reconnects,
        }


@dataclass(frozen=True)
class BurnInReport:
    running: bool
    started_at: datetime | None
    stopped_at: datetime | None
    elapsed_seconds: float
    cycles_executed: int
    average_cycle_ms: float
    min_cycle_ms: float
    max_cycle_ms: float
    errors: int
    exceptions: tuple[str, ...]
    reconnects: int
    memory_start_bytes: int
    memory_end_bytes: int
    memory_growth_bytes: int
    cpu_seconds: float
    cache_items: int
    queue_items: int
    event_count: int
    snapshot_count: int
    alerts: tuple[str, ...]
    cycle_metrics: tuple[BurnInCycleMetric, ...] = field(default_factory=tuple)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "elapsed_seconds": _finite(self.elapsed_seconds),
            "cycles_executed": self.cycles_executed,
            "average_cycle_ms": _finite(self.average_cycle_ms),
            "min_cycle_ms": _finite(self.min_cycle_ms),
            "max_cycle_ms": _finite(self.max_cycle_ms),
            "errors": self.errors,
            "exceptions": list(self.exceptions),
            "reconnects": self.reconnects,
            "memory_start_bytes": self.memory_start_bytes,
            "memory_end_bytes": self.memory_end_bytes,
            "memory_growth_bytes": self.memory_growth_bytes,
            "cpu_seconds": _finite(self.cpu_seconds),
            "cache_items": self.cache_items,
            "queue_items": self.queue_items,
            "event_count": self.event_count,
            "snapshot_count": self.snapshot_count,
            "alerts": list(self.alerts),
            "cycle_metrics": [item.to_public_dict() for item in self.cycle_metrics],
        }


class BurnInManager:
    def __init__(
        self, runtime: RuntimeEngine, config: BurnInConfig | None = None
    ) -> None:
        self.runtime = runtime
        self.config = config or BurnInConfig()
        self.running = False
        self.started_at: datetime | None = None
        self.stopped_at: datetime | None = None
        self._started_monotonic: float | None = None
        self._task: asyncio.Task[BurnInReport] | None = None
        self._cycle_metrics: list[BurnInCycleMetric] = []
        self._exceptions: list[str] = []
        self._alerts: list[str] = []
        self._memory_start_bytes = 0
        self._cpu_start_seconds = 0.0

    async def start(self) -> BurnInReport:
        if self.running:
            return self.report()
        self._prepare_start()
        try:
            await self._run_loop()
        finally:
            self._finish()
        return self.report()

    def start_background(self) -> BurnInReport:
        if not self.running:
            self._prepare_start()
            self._task = asyncio.create_task(self._run_background())
        return self.report()

    async def stop(self) -> BurnInReport:
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                self._alerts.append("burnin_cancelled")
        self.stopped_at = _utc_now()
        return self.report()

    async def _run_background(self) -> BurnInReport:
        try:
            await self._run_loop()
        finally:
            self._finish()
        return self.report()

    def _prepare_start(self) -> None:
        self.running = True
        self.started_at = _utc_now()
        self.stopped_at = None
        self._started_monotonic = time.monotonic()
        self._cycle_metrics.clear()
        self._exceptions.clear()
        self._alerts.clear()
        self._memory_start_bytes = _memory_bytes()
        self._cpu_start_seconds = time.process_time()

    def _finish(self) -> None:
        self.running = False
        self.stopped_at = _utc_now()

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "config": self.config.to_public_dict(),
            "report": self.report().to_public_dict(),
        }

    def report(self) -> BurnInReport:
        durations = [item.runtime_ms for item in self._cycle_metrics]
        memory_end = self._cycle_metrics[-1].memory_bytes if self._cycle_metrics else 0
        memory_start = self._memory_start_bytes if self._cycle_metrics else 0
        return BurnInReport(
            running=self.running,
            started_at=self.started_at,
            stopped_at=self.stopped_at,
            elapsed_seconds=self._elapsed_seconds(),
            cycles_executed=len(self._cycle_metrics),
            average_cycle_ms=sum(durations) / len(durations) if durations else 0.0,
            min_cycle_ms=min(durations) if durations else 0.0,
            max_cycle_ms=max(durations) if durations else 0.0,
            errors=sum(item.errors for item in self._cycle_metrics),
            exceptions=tuple(self._exceptions),
            reconnects=sum(item.reconnects for item in self._cycle_metrics),
            memory_start_bytes=memory_start,
            memory_end_bytes=memory_end,
            memory_growth_bytes=memory_end - memory_start,
            cpu_seconds=time.process_time() - self._cpu_start_seconds
            if self._cycle_metrics
            else 0.0,
            cache_items=self._cycle_metrics[-1].cache_items
            if self._cycle_metrics
            else 0,
            queue_items=self._cycle_metrics[-1].queue_items
            if self._cycle_metrics
            else 0,
            event_count=self._cycle_metrics[-1].event_count
            if self._cycle_metrics
            else 0,
            snapshot_count=self._cycle_metrics[-1].snapshot_count
            if self._cycle_metrics
            else 0,
            alerts=tuple(dict.fromkeys(self._alerts)),
            cycle_metrics=tuple(self._cycle_metrics[-self.config.max_events :]),
        )

    async def _run_loop(self) -> None:
        deadline = time.monotonic() + self.config.duration_seconds
        cycle_limit = self.config.max_cycles
        while self.running and time.monotonic() <= deadline:
            if cycle_limit is not None and len(self._cycle_metrics) >= cycle_limit:
                break
            await self._run_cycle()
            if self.config.cycle_sleep_seconds > 0:
                await asyncio.sleep(self.config.cycle_sleep_seconds)

    async def _run_cycle(self) -> None:
        cycle_number = len(self._cycle_metrics) + 1
        start = time.perf_counter()
        cpu_start = time.process_time()
        try:
            await self.runtime.run_once()
        except Exception as exc:
            self._exceptions.append(type(exc).__name__)
            self.runtime.system.watchdog.record_error("BurnIn")
        elapsed_ms = (time.perf_counter() - start) * 1000
        metric = BurnInCycleMetric(
            cycle=cycle_number,
            timestamp=_utc_now(),
            runtime_ms=elapsed_ms,
            cpu_seconds=time.process_time() - cpu_start,
            memory_bytes=_memory_bytes(),
            cache_items=_runtime_cache_items(self.runtime),
            queue_items=_runtime_queue_items(self.runtime),
            event_count=len(self.runtime.system.events.events),
            snapshot_count=len(self.runtime.system.snapshots.snapshots),
            errors=sum(self.runtime.system.watchdog.errors.values()),
            reconnects=sum(self.runtime.system.watchdog.reconnects.values()),
        )
        self._cycle_metrics.append(metric)
        self._validate_stability(metric)

    def _validate_stability(self, metric: BurnInCycleMetric) -> None:
        if (
            metric.memory_bytes - self._memory_start_bytes
            > self.config.memory_growth_alert_bytes
        ):
            self._alerts.append("memory_growth_threshold_exceeded")
        if metric.cache_items > self.config.max_events:
            self._alerts.append("cache_growth_threshold_exceeded")
        if metric.event_count >= self.config.max_events:
            self._alerts.append("event_queue_at_capacity")
        if self.runtime.last_error:
            self._alerts.append("runtime_errors_detected")

    def _elapsed_seconds(self) -> float:
        if self._started_monotonic is None:
            return 0.0
        return time.monotonic() - self._started_monotonic


def _runtime_cache_items(runtime: RuntimeEngine) -> int:
    history = getattr(runtime, "history", {})
    return sum(len(rows) for rows in history.values())


def _runtime_queue_items(runtime: RuntimeEngine) -> int:
    return len(getattr(runtime.system.events, "events", ()))


def _memory_bytes() -> int:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports KiB, macOS reports bytes. Containers here are Linux, but keep
    # the value sane if a platform already returns bytes.
    return int(usage * 1024 if usage < 10_000_000 else usage)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _finite(value: float) -> float:
    return value if math.isfinite(value) else 0.0
