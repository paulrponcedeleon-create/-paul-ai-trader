"""add simulated position close fields

Revision ID: 20260720_0002
Revises: 20260720_0001
Create Date: 2026-07-20 00:00:01.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0002"
down_revision: Union[str, None] = "20260720_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "simulated_orders",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "simulated_orders",
        sa.Column("close_price", sa.Float(), nullable=True),
    )
    op.add_column(
        "simulated_orders",
        sa.Column("realized_pnl_mxn", sa.Float(), nullable=True),
    )
    op.create_index(
        "ix_simulated_orders_status",
        "simulated_orders",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_simulated_orders_status", table_name="simulated_orders")
    op.drop_column("simulated_orders", "realized_pnl_mxn")
    op.drop_column("simulated_orders", "close_price")
    op.drop_column("simulated_orders", "closed_at")
