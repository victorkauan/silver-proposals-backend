"""add share links

Revision ID: fe4037357d01
Revises: 7d0a19ff327d
Create Date: 2026-11-17 21:56:07.660215
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fe4037357d01"
down_revision: str | None = "7d0a19ff327d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "share_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_share_links_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["proposals.id"],
            name=op.f("fk_share_links_proposal_id_proposals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_share_links")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_share_links_token_hash")),
    )
    op.create_index(
        op.f("ix_share_links_proposal_id"), "share_links", ["proposal_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_share_links_proposal_id"), table_name="share_links")
    op.drop_table("share_links")
