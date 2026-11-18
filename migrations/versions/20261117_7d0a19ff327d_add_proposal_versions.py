"""add proposal versions

Revision ID: 7d0a19ff327d
Revises: 3aff364e2f03
Create Date: 2026-11-17 21:48:06.934570
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7d0a19ff327d"
down_revision: str | None = "3aff364e2f03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "proposal_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "generated",
                "edited",
                "restored",
                name="version_source",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_proposal_versions_author_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["proposals.id"],
            name=op.f("fk_proposal_versions_proposal_id_proposals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proposal_versions")),
        sa.UniqueConstraint(
            "proposal_id", "number", name=op.f("uq_proposal_versions_proposal_id_number")
        ),
    )
    op.create_index(
        op.f("ix_proposal_versions_proposal_id"), "proposal_versions", ["proposal_id"], unique=False
    )
    op.add_column(
        "proposals", sa.Column("version", sa.Integer(), server_default="0", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("proposals", "version")
    op.drop_index(op.f("ix_proposal_versions_proposal_id"), table_name="proposal_versions")
    op.drop_table("proposal_versions")
