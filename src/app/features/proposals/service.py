import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy.orm import Session

from app.features.proposals import repository
from app.features.proposals.models import Proposal, ProposalRole
from app.shared.errors import AppError, ErrorCode

ROLE_RANK = {ProposalRole.VIEWER: 1, ProposalRole.EDITOR: 2, ProposalRole.OWNER: 3}


@dataclass(frozen=True)
class Access:
    proposal: Proposal
    role: ProposalRole


def authorize(
    session: Session, proposal_id: uuid.UUID, user_id: uuid.UUID, minimum: ProposalRole
) -> Access:
    found = repository.get_with_role(session, proposal_id, user_id)
    if found is None:
        # Non-members get 404 so they cannot tell whether the proposal exists.
        raise AppError(ErrorCode.PROPOSAL_NOT_FOUND, status.HTTP_404_NOT_FOUND)
    proposal, role = found
    if ROLE_RANK[role] < ROLE_RANK[minimum]:
        raise AppError(ErrorCode.FORBIDDEN, status.HTTP_403_FORBIDDEN)
    return Access(proposal, role)


def create(
    session: Session, owner_id: uuid.UUID, title: str, client_name: str, briefing: str
) -> Access:
    proposal = repository.add_proposal(session, owner_id, title, client_name, briefing)
    session.commit()
    session.refresh(proposal)
    return Access(proposal, ProposalRole.OWNER)


def update(session: Session, access: Access, title: str | None, client_name: str | None) -> Access:
    if title is not None:
        access.proposal.title = title
    if client_name is not None:
        access.proposal.client_name = client_name
    session.commit()
    session.refresh(access.proposal)
    return access


def set_archived(session: Session, access: Access, archived: bool) -> Access:
    access.proposal.archived_at = datetime.now(UTC) if archived else None
    session.commit()
    session.refresh(access.proposal)
    return access


def delete(session: Session, access: Access) -> None:
    repository.delete(session, access.proposal)
    session.commit()
