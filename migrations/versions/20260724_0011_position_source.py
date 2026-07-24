"""persist manual, runtime, or exploration origin on simulated positions

Revision ID: 20260724_0011
Revises: 20260723_0010
Create Date: 2026-07-24 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260724_0011"
down_revision: Union[str, None] = "20260723_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("simulated_orders") as batch_op:
        batch_op.add_column(sa.Column("source", sa.String(length=32), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE simulated_orders
            SET source = CASE
                WHEN lower(coalesce(risk_check, '')) LIKE 'paper_exploration_%'
                    THEN 'exploration'
                WHEN lower(coalesce(risk_check, '')) IN ('strategy_buy', 'strategy_sell')
                    THEN 'runtime'
                WHEN lower(coalesce(risk_check, '')) LIKE 'runtime_%'
                    THEN 'runtime'
                WHEN correlation_id IS NOT NULL
                     AND lower(coalesce(risk_check, '')) LIKE '%strategy%'
                    THEN 'runtime'
                ELSE 'manual'
            END
            WHERE source IS NULL
            """
        )
    )

    with op.batch_alter_table("simulated_orders") as batch_op:
        batch_op.alter_column(
            "source",
            existing_type=sa.String(length=32),
            nullable=False,
        )
        batch_op.create_index(
            "ix_simulated_orders_source",
            ["source"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("simulated_orders") as batch_op:
        batch_op.drop_index("ix_simulated_orders_source")
        batch_op.drop_column("source")
