"""add parent position linkage for partial sells

Revision ID: 20260723_0010
Revises: 20260723_0009
Create Date: 2026-07-23 23:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260723_0010"
down_revision: Union[str, None] = "20260723_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("simulated_orders") as batch_op:
        batch_op.add_column(sa.Column("parent_position_id", sa.String(length=40), nullable=True))
        batch_op.create_index(
            "ix_simulated_orders_parent_position_id",
            ["parent_position_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("simulated_orders") as batch_op:
        batch_op.drop_index("ix_simulated_orders_parent_position_id")
        batch_op.drop_column("parent_position_id")
