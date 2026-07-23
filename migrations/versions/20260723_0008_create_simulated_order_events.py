"""create simulated order events table

Revision ID: 20260723_0008
Revises: 20260722_0007
Create Date: 2026-07-23 23:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260723_0008"
down_revision: Union[str, None] = "20260722_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulated_order_events",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("position_id", sa.String(length=40), nullable=True),
        sa.Column("book", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("amount_mxn", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("fee_mxn", sa.Float(), nullable=True),
        sa.Column("realized_pnl_mxn", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulated_order_events_created_at",
        "simulated_order_events",
        ["created_at"],
    )
    op.create_index(
        "ix_simulated_order_events_position_id",
        "simulated_order_events",
        ["position_id"],
    )
    op.create_index(
        "ix_simulated_order_events_book", "simulated_order_events", ["book"]
    )
    op.create_index(
        "ix_simulated_order_events_side", "simulated_order_events", ["side"]
    )
    op.create_index(
        "ix_simulated_order_events_status", "simulated_order_events", ["status"]
    )
    op.create_index(
        "ix_simulated_order_events_source", "simulated_order_events", ["source"]
    )
    op.create_index(
        "ix_simulated_order_events_correlation_id",
        "simulated_order_events",
        ["correlation_id"],
    )
    _backfill_existing_simulations()


def _backfill_existing_simulations() -> None:
    connection = op.get_bind()
    simulations = sa.table(
        "simulated_orders",
        sa.column("id", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("closed_at", sa.DateTime(timezone=True)),
        sa.column("book", sa.String()),
        sa.column("amount_mxn", sa.Float()),
        sa.column("reference_price", sa.Float()),
        sa.column("close_price", sa.Float()),
        sa.column("entry_fee_mxn", sa.Float()),
        sa.column("exit_fee_mxn", sa.Float()),
        sa.column("realized_pnl_mxn", sa.Float()),
        sa.column("status", sa.String()),
        sa.column("correlation_id", sa.String()),
    )
    events = sa.table(
        "simulated_order_events",
        sa.column("id", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("position_id", sa.String()),
        sa.column("book", sa.String()),
        sa.column("side", sa.String()),
        sa.column("status", sa.String()),
        sa.column("amount_mxn", sa.Float()),
        sa.column("price", sa.Float()),
        sa.column("fee_mxn", sa.Float()),
        sa.column("realized_pnl_mxn", sa.Float()),
        sa.column("source", sa.String()),
        sa.column("reason", sa.String()),
        sa.column("correlation_id", sa.String()),
    )
    rows = connection.execute(sa.select(simulations)).mappings().all()
    payloads: list[dict[str, object]] = []
    for row in rows:
        position_id = str(row["id"])
        payloads.append(
            {
                "id": f"b_{position_id}",
                "created_at": row["created_at"],
                "position_id": position_id,
                "book": row["book"],
                "side": "buy",
                "status": "filled",
                "amount_mxn": row["amount_mxn"],
                "price": row["reference_price"],
                "fee_mxn": row["entry_fee_mxn"],
                "realized_pnl_mxn": None,
                "source": "history",
                "reason": "historical_buy",
                "correlation_id": row["correlation_id"],
            }
        )
        if row["status"] == "closed" and row["closed_at"] is not None:
            payloads.append(
                {
                    "id": f"s_{position_id}",
                    "created_at": row["closed_at"],
                    "position_id": position_id,
                    "book": row["book"],
                    "side": "sell",
                    "status": "filled",
                    "amount_mxn": row["amount_mxn"],
                    "price": row["close_price"],
                    "fee_mxn": row["exit_fee_mxn"],
                    "realized_pnl_mxn": row["realized_pnl_mxn"],
                    "source": "history",
                    "reason": "historical_close",
                    "correlation_id": row["correlation_id"],
                }
            )
    if payloads:
        connection.execute(sa.insert(events), payloads)


def downgrade() -> None:
    op.drop_index(
        "ix_simulated_order_events_correlation_id",
        table_name="simulated_order_events",
    )
    op.drop_index("ix_simulated_order_events_source", table_name="simulated_order_events")
    op.drop_index("ix_simulated_order_events_status", table_name="simulated_order_events")
    op.drop_index("ix_simulated_order_events_side", table_name="simulated_order_events")
    op.drop_index("ix_simulated_order_events_book", table_name="simulated_order_events")
    op.drop_index(
        "ix_simulated_order_events_position_id",
        table_name="simulated_order_events",
    )
    op.drop_index(
        "ix_simulated_order_events_created_at",
        table_name="simulated_order_events",
    )
    op.drop_table("simulated_order_events")
