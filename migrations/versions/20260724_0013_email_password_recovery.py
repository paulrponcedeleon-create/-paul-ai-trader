"""add account email and one-time password recovery

Revision ID: 20260724_0013
Revises: 20260724_0012
Create Date: 2026-07-24 16:55:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260724_0013"
down_revision: Union[str, None] = "20260724_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user_accounts") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=254), nullable=True))
        batch_op.add_column(
            sa.Column("password_reset_token_hash", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("password_reset_requested_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index("ix_user_accounts_email", ["email"], unique=True)
        batch_op.create_index(
            "ix_user_accounts_password_reset_token_hash",
            ["password_reset_token_hash"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("user_accounts") as batch_op:
        batch_op.drop_index("ix_user_accounts_password_reset_token_hash")
        batch_op.drop_index("ix_user_accounts_email")
        batch_op.drop_column("password_changed_at")
        batch_op.drop_column("password_reset_expires_at")
        batch_op.drop_column("password_reset_requested_at")
        batch_op.drop_column("password_reset_token_hash")
        batch_op.drop_column("email")
