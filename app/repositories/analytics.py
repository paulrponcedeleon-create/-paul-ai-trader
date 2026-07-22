from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalyticsEventRow, AnalyticsSnapshotRow
from app.repositories.backtests import dumps_json, loads_json


class AnalyticsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_snapshot(self, *, period: str, metrics: dict[str, Any]) -> dict[str, Any]:
        row = AnalyticsSnapshotRow(period=period, metrics_json=dumps_json(metrics))
        self.session.add(row)
        self.session.flush()
        return _snapshot(row)

    def list_snapshots(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(AnalyticsSnapshotRow)
            .order_by(AnalyticsSnapshotRow.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return [_snapshot(row) for row in rows]

    def snapshots_by_range(
        self, start: datetime | None = None, end: datetime | None = None
    ) -> list[dict[str, Any]]:
        query = select(AnalyticsSnapshotRow)
        if start is not None:
            query = query.where(AnalyticsSnapshotRow.created_at >= start)
        if end is not None:
            query = query.where(AnalyticsSnapshotRow.created_at <= end)
        return [_snapshot(row) for row in self.session.scalars(query).all()]

    def save_event(
        self,
        *,
        timestamp: datetime,
        category: str,
        event_type: str,
        severity: str,
        source: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = AnalyticsEventRow(
            timestamp=timestamp,
            category=category,
            event_type=event_type,
            severity=severity,
            source=source,
            message=message,
            metadata_json=dumps_json(metadata or {}),
        )
        self.session.add(row)
        self.session.flush()
        return _event(row)

    def list_events(
        self,
        *,
        category: str | None = None,
        severity: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query = select(AnalyticsEventRow)
        if category is not None:
            query = query.where(AnalyticsEventRow.category == category)
        if severity is not None:
            query = query.where(AnalyticsEventRow.severity == severity)
        if start is not None:
            query = query.where(AnalyticsEventRow.timestamp >= start)
        if end is not None:
            query = query.where(AnalyticsEventRow.timestamp <= end)
        rows = self.session.scalars(
            query.order_by(AnalyticsEventRow.timestamp.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return [_event(row) for row in rows]


def _snapshot(row: AnalyticsSnapshotRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "period": row.period,
        "metrics": loads_json(row.metrics_json),
    }


def _event(row: AnalyticsEventRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "timestamp": row.timestamp,
        "category": row.category,
        "event_type": row.event_type,
        "severity": row.severity,
        "source": row.source,
        "message": row.message,
        "metadata": loads_json(row.metadata_json),
    }
