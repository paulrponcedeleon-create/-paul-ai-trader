"""use decimal numeric columns for simulated accounting

Revision ID: 20260723_0009
Revises: 20260723_0008
Create Date: 2026-07-23 23:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260723_0009"
down_revision: Union[str, None] = "20260723_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MONEY = sa.Numeric(precision=20, scale=2)
PRICE = sa.Numeric(precision=30, scale=12)
RATE = sa.Numeric(precision=18, scale=12)

SIMULATED_ORDER_COLUMNS = (
    ("amount_mxn", MONEY, False),
    ("reference_price", PRICE, True),
    ("close_price", PRICE, True),
    ("entry_fee_rate", RATE, True),
    ("entry_fee_mxn", MONEY, True),
    ("exit_fee_rate", RATE, True),
    ("exit_fee_mxn", MONEY, True),
    ("realized_pnl_mxn", MONEY, True),
)

ORDER_EVENT_COLUMNS = (
    ("amount_mxn", MONEY, False),
    ("price", PRICE, True),
    ("fee_mxn", MONEY, True),
    ("realized_pnl_mxn", MONEY, True),
)


def _alter_to_numeric(table_name: str, columns) -> None:
    is_postgresql = op.get_bind().dialect.name == "postgresql"
    with op.batch_alter_table(table_name) as batch_op:
        for column_name, target_type, nullable in columns:
            kwargs = {
                "existing_type": sa.Float(),
                "type_": target_type,
                "existing_nullable": nullable,
            }
            if is_postgresql:
                kwargs["postgresql_using"] = f"{column_name}::numeric"
            batch_op.alter_column(column_name, **kwargs)


def _alter_to_float(table_name: str, columns) -> None:
    is_postgresql = op.get_bind().dialect.name == "postgresql"
    with op.batch_alter_table(table_name) as batch_op:
        for column_name, existing_type, nullable in columns:
            kwargs = {
                "existing_type": existing_type,
                "type_": sa.Float(),
                "existing_nullable": nullable,
            }
            if is_postgresql:
                kwargs["postgresql_using"] = f"{column_name}::double precision"
            batch_op.alter_column(column_name, **kwargs)


def upgrade() -> None:
    _alter_to_numeric("simulated_orders", SIMULATED_ORDER_COLUMNS)
    _alter_to_numeric("simulated_order_events", ORDER_EVENT_COLUMNS)


def downgrade() -> None:
    _alter_to_float("simulated_order_events", ORDER_EVENT_COLUMNS)
    _alter_to_float("simulated_orders", SIMULATED_ORDER_COLUMNS)
