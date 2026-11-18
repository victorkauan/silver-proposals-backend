import uuid

from fastapi import status
from sqlalchemy.orm import Session

from app.features.proposals.models import Proposal, ProposalVersion, VersionSource
from app.features.versions import repository
from app.shared.errors import AppError, ErrorCode


def record_version(
    session: Session,
    proposal: Proposal,
    content: str,
    source: VersionSource,
    author_id: uuid.UUID | None,
) -> ProposalVersion:
    proposal.version += 1
    proposal.content = content
    version = ProposalVersion(
        proposal_id=proposal.id,
        number=proposal.version,
        content=content,
        source=source,
        author_id=author_id,
    )
    session.add(version)
    return version


def _locked(session: Session, proposal_id: uuid.UUID) -> Proposal:
    proposal = repository.lock_proposal(session, proposal_id)
    if proposal is None:
        raise AppError(ErrorCode.PROPOSAL_NOT_FOUND, status.HTTP_404_NOT_FOUND)
    return proposal


def save_content(
    session: Session,
    proposal_id: uuid.UUID,
    content: str,
    base_version: int,
    author_id: uuid.UUID,
) -> Proposal:
    proposal = _locked(session, proposal_id)
    if proposal.version != base_version:
        session.rollback()
        raise AppError(ErrorCode.VERSION_CONFLICT, status.HTTP_409_CONFLICT)
    if content != proposal.content:
        record_version(session, proposal, content, VersionSource.EDITED, author_id)
    session.commit()
    session.refresh(proposal)
    return proposal


def get_version(
    session: Session, proposal_id: uuid.UUID, number: int
) -> tuple[ProposalVersion, str | None]:
    found = repository.get_version(session, proposal_id, number)
    if found is None:
        raise AppError(ErrorCode.VERSION_NOT_FOUND, status.HTTP_404_NOT_FOUND)
    return found


def restore(
    session: Session, proposal_id: uuid.UUID, number: int, author_id: uuid.UUID
) -> Proposal:
    version, _ = get_version(session, proposal_id, number)
    proposal = _locked(session, proposal_id)
    record_version(session, proposal, version.content, VersionSource.RESTORED, author_id)
    session.commit()
    session.refresh(proposal)
    return proposal
