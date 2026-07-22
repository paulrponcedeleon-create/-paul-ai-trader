"""create analytics tables

Revision ID: 20260722_0007
Revises: 20260722_0006
Create Date: 2026-07-22 00:07:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260722_0007"
down_revision: Union[str, None] = "20260722_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analytics_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period", sa.String(length=32), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_snapshots_created_at", "analytics_snapshots", ["created_at"])
    op.create_index("ix_analytics_snapshots_period", "analytics_snapshots", ["period"])
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_events_category", "analytics_events", ["category"])
    op.create_index("ix_analytics_events_event_type", "analytics_events", ["event_type"])
    op.create_index("ix_analytics_events_severity", "analytics_events", ["severity"])
    op.create_index("ix_analytics_events_source", "analytics_events", ["source"])
    op.create_index("ix_analytics_events_timestamp", "analytics_events", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_analytics_events_timestamp", table_name="analytics_events")
    op.drop_index("ix_analytics_events_source", table_name="analytics_events")
    op.drop_index("ix_analytics_events_severity", table_name="analytics_events")
    op.drop_index("ix_analytics_events_event_type", table_name="analytics_events")
    op.drop_index("ix_analytics_events_category", table_name="analytics_events")
    op.drop_table("analytics_events")
    op.drop_index("ix_analytics_snapshots_period", table_name="analytics_snapshots")
    op.drop_index("ix_analytics_snapshots_created_at", table_name="analytics_snapshots")
    op.drop_table("analytics_snapshots")
