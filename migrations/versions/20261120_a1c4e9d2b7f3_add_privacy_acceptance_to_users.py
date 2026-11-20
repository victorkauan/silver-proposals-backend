"""add privacy acceptance to users

Revision ID: a1c4e9d2b7f3
Revises: fe4037357d01
Create Date: 2026-11-20 18:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c4e9d2b7f3"
down_revision: str | None = "fe4037357d01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("privacy_version", sa.String(length=20), nullable=True))
    op.add_column(
        "users", sa.Column("privacy_accepted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        op.f("ix_refresh_tokens_expires_at"), "refresh_tokens", ["expires_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_tokens_expires_at"), table_name="refresh_tokens")
    op.drop_column("users", "privacy_accepted_at")
    op.drop_column("users", "privacy_version")
