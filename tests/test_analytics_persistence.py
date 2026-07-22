from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytest.importorskip("sqlalchemy")

pytestmark = pytest.mark.database

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.repositories.analytics import AnalyticsRepository


def test_analytics_repository_snapshots_and_events(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'analytics.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        repo = AnalyticsRepository(session)
        repo.save_snapshot(period="day", metrics={"net_profit": 1})
        repo.save_event(
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            category="system",
            event_type="test",
            severity="info",
            source="test",
            message="ok",
        )
        session.commit()
        assert repo.list_snapshots()[0]["metrics"] == {"net_profit": 1}
        assert repo.list_events(category="system")[0]["message"] == "ok"
