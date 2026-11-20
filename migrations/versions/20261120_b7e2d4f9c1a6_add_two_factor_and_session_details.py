"""add two-factor authentication and session details

Revision ID: b7e2d4f9c1a6
Revises: a1c4e9d2b7f3
Create Date: 2026-11-20 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2d4f9c1a6"
down_revision: str | None = "a1c4e9d2b7f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("totp_secret", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("totp_pending_secret", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("totp_last_step", sa.BigInteger(), nullable=True))
    op.add_column(
        "refresh_tokens",
        sa.Column(
            "session_started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.execute("""
        UPDATE refresh_tokens AS token
        SET session_started_at = family.started_at
        FROM (
            SELECT family_id, min(created_at) AS started_at
            FROM refresh_tokens
            GROUP BY family_id
        ) AS family
        WHERE token.family_id = family.family_id
    """)
    op.add_column("refresh_tokens", sa.Column("user_agent", sa.String(length=255), nullable=True))
    op.create_table(
        "recovery_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recovery_codes_user_id"), "recovery_codes", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_recovery_codes_user_id"), table_name="recovery_codes")
    op.drop_table("recovery_codes")
    op.drop_column("refresh_tokens", "user_agent")
    op.drop_column("refresh_tokens", "session_started_at")
    op.drop_column("users", "totp_last_step")
    op.drop_column("users", "totp_enabled_at")
    op.drop_column("users", "totp_pending_secret")
    op.drop_column("users", "totp_secret")
