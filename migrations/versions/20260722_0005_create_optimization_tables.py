"""create optimization tables

Revision ID: 20260722_0005
Revises: 20260721_0004
Create Date: 2026-07-22 00:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260722_0005"
down_revision: Union[str, None] = "20260721_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "optimization_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("strategy_name", sa.String(length=120), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("dataset_id", sa.String(length=255), nullable=False),
        sa.Column("parameter_space_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("results_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_optimization_runs_created_at", "optimization_runs", ["created_at"])
    op.create_index("ix_optimization_runs_dataset_id", "optimization_runs", ["dataset_id"])
    op.create_index("ix_optimization_runs_status", "optimization_runs", ["status"])
    op.create_index("ix_optimization_runs_strategy_name", "optimization_runs", ["strategy_name"])

    op.create_table(
        "optimization_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("optimization_run_id", sa.Integer(), nullable=False),
        sa.Column("strategy_name", sa.String(length=120), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=False),
        sa.Column("total_return_pct", sa.Float(), nullable=False),
        sa.Column("max_drawdown_pct", sa.Float(), nullable=False),
        sa.Column("sharpe", sa.Float(), nullable=False),
        sa.Column("profit_factor", sa.Float(), nullable=True),
        sa.Column("win_rate_pct", sa.Float(), nullable=False),
        sa.Column("trades_count", sa.Integer(), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["optimization_run_id"], ["optimization_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_optimization_results_composite_score", "optimization_results", ["composite_score"])
    op.create_index("ix_optimization_results_optimization_run_id", "optimization_results", ["optimization_run_id"])
    op.create_index("ix_optimization_results_strategy_name", "optimization_results", ["strategy_name"])


def downgrade() -> None:
    op.drop_index("ix_optimization_results_strategy_name", table_name="optimization_results")
    op.drop_index("ix_optimization_results_optimization_run_id", table_name="optimization_results")
    op.drop_index("ix_optimization_results_composite_score", table_name="optimization_results")
    op.drop_table("optimization_results")
    op.drop_index("ix_optimization_runs_strategy_name", table_name="optimization_runs")
    op.drop_index("ix_optimization_runs_status", table_name="optimization_runs")
    op.drop_index("ix_optimization_runs_dataset_id", table_name="optimization_runs")
    op.drop_index("ix_optimization_runs_created_at", table_name="optimization_runs")
    op.drop_table("optimization_runs")
