"""create backtest tables

Revision ID: 20260721_0004
Revises: 20260720_0003
Create Date: 2026-07-21 00:04:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260721_0004"
down_revision: Union[str, None] = "20260720_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("strategy_name", sa.String(length=120), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("book", sa.String(length=32), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initial_capital_mxn", sa.Float(), nullable=False),
        sa.Column("final_capital_mxn", sa.Float(), nullable=True),
        sa.Column("total_return_pct", sa.Float(), nullable=True),
        sa.Column("max_drawdown_pct", sa.Float(), nullable=True),
        sa.Column("win_rate_pct", sa.Float(), nullable=True),
        sa.Column("trades_count", sa.Integer(), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backtest_runs_book", "backtest_runs", ["book"])
    op.create_index("ix_backtest_runs_created_at", "backtest_runs", ["created_at"])
    op.create_index("ix_backtest_runs_status", "backtest_runs", ["status"])
    op.create_index("ix_backtest_runs_strategy_name", "backtest_runs", ["strategy_name"])

    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("backtest_run_id", sa.Integer(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("book", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=False),
        sa.Column("amount_mxn", sa.Float(), nullable=False),
        sa.Column("pnl_mxn", sa.Float(), nullable=False),
        sa.Column("return_pct", sa.Float(), nullable=False),
        sa.Column("fees_mxn", sa.Float(), nullable=False),
        sa.Column("signal_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["backtest_run_id"], ["backtest_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backtest_trades_backtest_run_id", "backtest_trades", ["backtest_run_id"])
    op.create_index("ix_backtest_trades_book", "backtest_trades", ["book"])
    op.create_index("ix_backtest_trades_closed_at", "backtest_trades", ["closed_at"])
    op.create_index("ix_backtest_trades_opened_at", "backtest_trades", ["opened_at"])


def downgrade() -> None:
    op.drop_index("ix_backtest_trades_opened_at", table_name="backtest_trades")
    op.drop_index("ix_backtest_trades_closed_at", table_name="backtest_trades")
    op.drop_index("ix_backtest_trades_book", table_name="backtest_trades")
    op.drop_index("ix_backtest_trades_backtest_run_id", table_name="backtest_trades")
    op.drop_table("backtest_trades")
    op.drop_index("ix_backtest_runs_strategy_name", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_status", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_created_at", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_book", table_name="backtest_runs")
    op.drop_table("backtest_runs")
