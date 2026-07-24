"""add users, per-user simulations, bot preferences and encrypted credentials

Revision ID: 20260724_0012
Revises: 20260724_0011
Create Date: 2026-07-24 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260724_0012"
down_revision: Union[str, None] = "20260724_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_accounts",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("bot_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "ai_exploration_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "shared_learning_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "simulated_initial_capital_mxn",
            sa.Numeric(20, 2),
            nullable=False,
            server_default="5000.00",
        ),
        sa.Column("bitso_api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("bitso_api_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("bitso_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_accounts_username", "user_accounts", ["username"], unique=True)
    op.create_index("ix_user_accounts_is_active", "user_accounts", ["is_active"], unique=False)
    op.create_index("ix_user_accounts_created_at", "user_accounts", ["created_at"], unique=False)

    op.execute(
        sa.text(
            """
            INSERT INTO user_accounts (
                id, username, display_name, password_hash, is_admin, is_active,
                bot_enabled, ai_exploration_enabled, shared_learning_enabled,
                simulated_initial_capital_mxn, created_at, updated_at
            ) VALUES (
                'owner', 'paul', 'Paul', 'environment_bootstrap',
                true, true, true, true, true, 5000.00,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """
        )
    )

    with op.batch_alter_table("simulated_orders") as batch_op:
        batch_op.add_column(
            sa.Column("user_id", sa.String(length=40), nullable=True)
        )
    op.execute(sa.text("UPDATE simulated_orders SET user_id = 'owner' WHERE user_id IS NULL"))
    with op.batch_alter_table("simulated_orders") as batch_op:
        batch_op.alter_column(
            "user_id", existing_type=sa.String(length=40), nullable=False
        )
        batch_op.create_index("ix_simulated_orders_user_id", ["user_id"], unique=False)

    with op.batch_alter_table("simulated_order_events") as batch_op:
        batch_op.add_column(
            sa.Column("user_id", sa.String(length=40), nullable=True)
        )
    op.execute(
        sa.text(
            "UPDATE simulated_order_events SET user_id = 'owner' WHERE user_id IS NULL"
        )
    )
    with op.batch_alter_table("simulated_order_events") as batch_op:
        batch_op.alter_column(
            "user_id", existing_type=sa.String(length=40), nullable=False
        )
        batch_op.create_index(
            "ix_simulated_order_events_user_id", ["user_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("simulated_order_events") as batch_op:
        batch_op.drop_index("ix_simulated_order_events_user_id")
        batch_op.drop_column("user_id")
    with op.batch_alter_table("simulated_orders") as batch_op:
        batch_op.drop_index("ix_simulated_orders_user_id")
        batch_op.drop_column("user_id")
    op.drop_index("ix_user_accounts_created_at", table_name="user_accounts")
    op.drop_index("ix_user_accounts_is_active", table_name="user_accounts")
    op.drop_index("ix_user_accounts_username", table_name="user_accounts")
    op.drop_table("user_accounts")
