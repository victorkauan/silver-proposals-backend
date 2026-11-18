import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.features.proposals.models import Proposal, ProposalMember, ProposalRole


def add_proposal(
    session: Session, owner_id: uuid.UUID, title: str, client_name: str, briefing: str
) -> Proposal:
    proposal = Proposal(title=title, client_name=client_name, briefing=briefing, content="")
    session.add(proposal)
    session.flush()
    add_member(session, proposal.id, owner_id, ProposalRole.OWNER)
    return proposal


def add_member(
    session: Session, proposal_id: uuid.UUID, user_id: uuid.UUID, role: ProposalRole
) -> ProposalMember:
    member = ProposalMember(proposal_id=proposal_id, user_id=user_id, role=role)
    session.add(member)
    session.flush()
    return member


def get_with_role(
    session: Session, proposal_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Proposal, ProposalRole] | None:
    row = session.execute(
        select(Proposal, ProposalMember.role)
        .join(ProposalMember, ProposalMember.proposal_id == Proposal.id)
        .where(Proposal.id == proposal_id, ProposalMember.user_id == user_id)
    ).one_or_none()
    return (row[0], row[1]) if row else None


def list_for_user(
    session: Session, user_id: uuid.UUID, archived: bool, limit: int, offset: int
) -> tuple[list[tuple[Proposal, ProposalRole]], int]:
    condition = Proposal.archived_at.is_not(None) if archived else Proposal.archived_at.is_(None)
    base = (
        select(Proposal, ProposalMember.role)
        .join(ProposalMember, ProposalMember.proposal_id == Proposal.id)
        .where(ProposalMember.user_id == user_id, condition)
    )
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.execute(
        base.order_by(Proposal.updated_at.desc(), Proposal.id).limit(limit).offset(offset)
    ).all()
    return [(row[0], row[1]) for row in rows], total


def delete(session: Session, proposal: Proposal) -> None:
    session.delete(proposal)
