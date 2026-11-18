import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.proposals.models import Proposal
from app.features.sharing.models import ShareLink
from app.shared.errors import AppError, ErrorCode


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def is_active(link: ShareLink, now: datetime) -> bool:
    return link.revoked_at is None and link.expires_at > now


def create(
    session: Session, proposal_id: uuid.UUID, created_by: uuid.UUID, expires_in_days: int
) -> tuple[ShareLink, str]:
    token = secrets.token_urlsafe(32)
    link = ShareLink(
        proposal_id=proposal_id,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
        created_by=created_by,
    )
    session.add(link)
    session.commit()
    session.refresh(link)
    return link, token


def list_links(session: Session, proposal_id: uuid.UUID) -> list[ShareLink]:
    return list(
        session.scalars(
            select(ShareLink)
            .where(ShareLink.proposal_id == proposal_id)
            .order_by(ShareLink.created_at.desc())
        )
    )


def revoke(session: Session, proposal_id: uuid.UUID, link_id: uuid.UUID) -> None:
    link = session.scalar(
        select(ShareLink).where(ShareLink.id == link_id, ShareLink.proposal_id == proposal_id)
    )
    if link is None:
        raise AppError(ErrorCode.SHARE_LINK_NOT_FOUND, status.HTTP_404_NOT_FOUND)
    if link.revoked_at is None:
        link.revoked_at = datetime.now(UTC)
        session.commit()


def resolve(session: Session, token: str) -> Proposal:
    row = session.execute(
        select(ShareLink, Proposal)
        .join(Proposal, Proposal.id == ShareLink.proposal_id)
        .where(ShareLink.token_hash == hash_token(token))
    ).one_or_none()
    # Unknown, expired, revoked, and archived links answer the same, so a token reveals nothing.
    if row is None or not is_active(row[0], datetime.now(UTC)) or row[1].archived_at is not None:
        raise AppError(ErrorCode.SHARE_LINK_NOT_FOUND, status.HTTP_404_NOT_FOUND)
    return row[1]
