import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.features.auth.models import User
from app.features.proposals.models import Proposal, ProposalVersion


def lock_proposal(session: Session, proposal_id: uuid.UUID) -> Proposal | None:
    return session.scalars(
        select(Proposal)
        .where(Proposal.id == proposal_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()


def list_versions(
    session: Session, proposal_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[tuple[ProposalVersion, str | None]], int]:
    total = (
        session.scalar(
            select(func.count())
            .select_from(ProposalVersion)
            .where(ProposalVersion.proposal_id == proposal_id)
        )
        or 0
    )
    rows = session.execute(
        select(ProposalVersion, User.name)
        .outerjoin(User, User.id == ProposalVersion.author_id)
        .where(ProposalVersion.proposal_id == proposal_id)
        .order_by(ProposalVersion.number.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [(row[0], row[1]) for row in rows], total


def get_version(
    session: Session, proposal_id: uuid.UUID, number: int
) -> tuple[ProposalVersion, str | None] | None:
    row = session.execute(
        select(ProposalVersion, User.name)
        .outerjoin(User, User.id == ProposalVersion.author_id)
        .where(ProposalVersion.proposal_id == proposal_id, ProposalVersion.number == number)
    ).one_or_none()
    return (row[0], row[1]) if row else None
