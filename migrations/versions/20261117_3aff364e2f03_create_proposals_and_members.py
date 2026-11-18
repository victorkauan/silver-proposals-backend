"""create proposals and members

Revision ID: 3aff364e2f03
Revises: d940963d5d4c
Create Date: 2026-11-17 20:55:21.326461
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3aff364e2f03"
down_revision: str | None = "d940963d5d4c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("client_name", sa.String(length=200), nullable=False),
        sa.Column("briefing", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proposals")),
    )
    op.create_table(
        "proposal_members",
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "owner",
                "editor",
                "viewer",
                name="proposal_role",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["proposals.id"],
            name=op.f("fk_proposal_members_proposal_id_proposals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_proposal_members_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("proposal_id", "user_id", name=op.f("pk_proposal_members")),
    )
    op.create_index(
        op.f("ix_proposal_members_user_id"), "proposal_members", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_proposal_members_user_id"), table_name="proposal_members")
    op.drop_table("proposal_members")
    op.drop_table("proposals")
