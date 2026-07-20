"""create simulated orders table

Revision ID: 20260720_0001
Revises: 
Create Date: 2026-07-20 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulated_orders",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("book", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("amount_mxn", sa.Float(), nullable=False),
        sa.Column("reference_price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=True),
        sa.Column("signal_id", sa.String(length=64), nullable=True),
        sa.Column("risk_decision_id", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("risk_check", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_simulated_orders_book", "simulated_orders", ["book"], unique=False)
    op.create_index("ix_simulated_orders_correlation_id", "simulated_orders", ["correlation_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_simulated_orders_correlation_id", table_name="simulated_orders")
    op.drop_index("ix_simulated_orders_book", table_name="simulated_orders")
    op.drop_table("simulated_orders")
