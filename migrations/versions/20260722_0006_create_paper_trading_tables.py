"""create paper trading tables

Revision ID: 20260722_0006
Revises: 20260722_0005
Create Date: 2026-07-22 00:06:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260722_0006"
down_revision: Union[str, None] = "20260722_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_accounts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cash_mxn", sa.Float(), nullable=False),
        sa.Column("equity_mxn", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_accounts_status", "paper_accounts", ["status"])

    op.create_table(
        "paper_positions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("book", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("amount_mxn", sa.Float(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("realized_pnl_mxn", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["paper_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_positions_account_id", "paper_positions", ["account_id"])
    op.create_index("ix_paper_positions_book", "paper_positions", ["book"])
    op.create_index("ix_paper_positions_status", "paper_positions", ["status"])

    op.create_table(
        "paper_trades",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("position_id", sa.String(length=64), nullable=False),
        sa.Column("book", sa.String(length=32), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("pnl_mxn", sa.Float(), nullable=False),
        sa.Column("fees_mxn", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["paper_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_trades_account_id", "paper_trades", ["account_id"])
    op.create_index("ix_paper_trades_book", "paper_trades", ["book"])
    op.create_index("ix_paper_trades_position_id", "paper_trades", ["position_id"])

    op.create_table(
        "paper_orders",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("book", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_amount_mxn", sa.Float(), nullable=False),
        sa.Column("filled_quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["paper_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_orders_account_id", "paper_orders", ["account_id"])
    op.create_index("ix_paper_orders_book", "paper_orders", ["book"])
    op.create_index("ix_paper_orders_status", "paper_orders", ["status"])


def downgrade() -> None:
    op.drop_index("ix_paper_orders_status", table_name="paper_orders")
    op.drop_index("ix_paper_orders_book", table_name="paper_orders")
    op.drop_index("ix_paper_orders_account_id", table_name="paper_orders")
    op.drop_table("paper_orders")
    op.drop_index("ix_paper_trades_position_id", table_name="paper_trades")
    op.drop_index("ix_paper_trades_book", table_name="paper_trades")
    op.drop_index("ix_paper_trades_account_id", table_name="paper_trades")
    op.drop_table("paper_trades")
    op.drop_index("ix_paper_positions_status", table_name="paper_positions")
    op.drop_index("ix_paper_positions_book", table_name="paper_positions")
    op.drop_index("ix_paper_positions_account_id", table_name="paper_positions")
    op.drop_table("paper_positions")
    op.drop_index("ix_paper_accounts_status", table_name="paper_accounts")
    op.drop_table("paper_accounts")
