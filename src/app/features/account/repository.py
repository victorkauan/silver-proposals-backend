import uuid
from collections.abc import Sequence

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session, aliased

from app.features.auth.models import RefreshToken
from app.features.proposals.models import Proposal, ProposalMember, ProposalRole, ProposalVersion
from app.features.sharing.models import ShareLink


def sessions_of(session: Session, user_id: uuid.UUID) -> Sequence[RefreshToken]:
    return session.scalars(
        select(RefreshToken)
        .where(RefreshToken.user_id == user_id)
        .order_by(RefreshToken.created_at)
    ).all()


def proposals_of(session: Session, user_id: uuid.UUID) -> Sequence[tuple[Proposal, ProposalRole]]:
    rows = session.execute(
        select(Proposal, ProposalMember.role)
        .join(ProposalMember, ProposalMember.proposal_id == Proposal.id)
        .where(ProposalMember.user_id == user_id)
        .order_by(Proposal.created_at)
    ).all()
    return [(proposal, role) for proposal, role in rows]


def versions_by(session: Session, user_id: uuid.UUID) -> Sequence[ProposalVersion]:
    return session.scalars(
        select(ProposalVersion)
        .where(ProposalVersion.author_id == user_id)
        .order_by(ProposalVersion.created_at)
    ).all()


def share_links_by(session: Session, user_id: uuid.UUID) -> Sequence[ShareLink]:
    return session.scalars(
        select(ShareLink).where(ShareLink.created_by == user_id).order_by(ShareLink.created_at)
    ).all()


def delete_sole_owned_proposals(session: Session, user_id: uuid.UUID) -> int:
    other = aliased(ProposalMember)
    sole_owned = (
        select(ProposalMember.proposal_id)
        .where(ProposalMember.user_id == user_id, ProposalMember.role == ProposalRole.OWNER)
        .where(
            ~exists().where(
                other.proposal_id == ProposalMember.proposal_id,
                other.role == ProposalRole.OWNER,
                other.user_id != user_id,
            )
        )
    )
    ids = session.scalars(sole_owned).all()
    if ids:
        session.execute(delete(Proposal).where(Proposal.id.in_(ids)))
    return len(ids)
