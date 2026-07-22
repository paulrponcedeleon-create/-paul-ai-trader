from __future__ import annotations

from decimal import Decimal

from app.analytics.models import AnalyticsEvent, BrokerPerformance
from app.analytics.performance import q
from app.brokers.interface import BrokerInterface


class BrokerAnalyticsEngine:
    def calculate(
        self,
        broker: BrokerInterface | None = None,
        events: list[AnalyticsEvent] | None = None,
    ) -> BrokerPerformance:
        events = events or []
        broker_events = [e for e in events if e.category == "broker"]
        accepted = sum(1 for e in broker_events if e.event_type == "accepted")
        rejected = sum(1 for e in broker_events if e.event_type == "rejected")
        cancelled = sum(1 for e in broker_events if e.event_type == "cancelled")
        errors = [e for e in broker_events if e.severity in {"error", "critical"}]
        latencies = [
            float(e.metadata["latency_ms"])
            for e in broker_events
            if "latency_ms" in e.metadata
        ]
        health = broker.health() if broker is not None else None
        notes = tuple(health.errors) if health else tuple()
        requests = len(broker_events)
        return BrokerPerformance(
            broker.name if broker else "unknown",
            requests,
            accepted,
            rejected,
            cancelled,
            len(errors),
            sum(latencies) / len(latencies) if latencies else None,
            min(latencies) if latencies else None,
            max(latencies) if latencies else None,
            q(Decimal(accepted) / Decimal(requests) * Decimal("100"))
            if requests
            else Decimal("0"),
            q(Decimal(rejected) / Decimal(requests) * Decimal("100"))
            if requests
            else Decimal("0"),
            errors[-1].message if errors else None,
            broker_events[-1].message if broker_events else None,
            health.connected if health else False,
            None,
            notes,
        )
