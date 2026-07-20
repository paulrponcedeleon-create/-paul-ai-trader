"""add simulated trading fee fields

Revision ID: 20260720_0003
Revises: 20260720_0002
Create Date: 2026-07-20 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0003"
down_revision: Union[str, None] = "20260720_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("simulated_orders", sa.Column("entry_fee_rate", sa.Float(), nullable=True))
    op.add_column("simulated_orders", sa.Column("entry_fee_mxn", sa.Float(), nullable=True))
    op.add_column("simulated_orders", sa.Column("exit_fee_rate", sa.Float(), nullable=True))
    op.add_column("simulated_orders", sa.Column("exit_fee_mxn", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("simulated_orders", "exit_fee_mxn")
    op.drop_column("simulated_orders", "exit_fee_rate")
    op.drop_column("simulated_orders", "entry_fee_mxn")
    op.drop_column("simulated_orders", "entry_fee_rate")
