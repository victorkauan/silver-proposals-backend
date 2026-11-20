import logging
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy.orm import Session

from app.features.account import repository
from app.features.account.schemas import (
    AccountExport,
    ExportedAccount,
    ExportedProposal,
    ExportedSession,
    ExportedShareLink,
    ExportedVersion,
)
from app.features.auth import repository as auth_repository
from app.features.auth import security
from app.features.auth.models import User
from app.features.auth.service import accept_privacy, normalize_email
from app.shared.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)


def _confirm_password(user: User, password: str) -> None:
    if not security.verify_password(user.password_hash, password):
        raise AppError(ErrorCode.INVALID_PASSWORD, status.HTTP_403_FORBIDDEN)


def update_profile(session: Session, user: User, name: str) -> User:
    user.name = name
    session.commit()
    session.refresh(user)
    return user


def change_email(session: Session, user: User, email: str, password: str) -> User:
    _confirm_password(user, password)
    email = normalize_email(email)
    existing = auth_repository.get_user_by_email(session, email)
    if existing is not None and existing.id != user.id:
        raise AppError(ErrorCode.EMAIL_TAKEN, status.HTTP_409_CONFLICT)
    user.email = email
    session.commit()
    session.refresh(user)
    return user


def accept_current_privacy_notice(session: Session, user: User) -> User:
    accept_privacy(user)
    session.commit()
    session.refresh(user)
    return user


def export(session: Session, user: User) -> AccountExport:
    return AccountExport(
        exported_at=datetime.now(UTC),
        account=ExportedAccount.model_validate(user, from_attributes=True),
        sessions=[
            ExportedSession.model_validate(token, from_attributes=True)
            for token in repository.sessions_of(session, user.id)
        ],
        proposals=[
            ExportedProposal(
                id=proposal.id,
                role=role,
                title=proposal.title,
                client_name=proposal.client_name,
                briefing=proposal.briefing,
                content=proposal.content,
                version=proposal.version,
                archived_at=proposal.archived_at,
                created_at=proposal.created_at,
                updated_at=proposal.updated_at,
            )
            for proposal, role in repository.proposals_of(session, user.id)
        ],
        authored_versions=[
            ExportedVersion.model_validate(version, from_attributes=True)
            for version in repository.versions_by(session, user.id)
        ],
        share_links_created=[
            ExportedShareLink.model_validate(link, from_attributes=True)
            for link in repository.share_links_by(session, user.id)
        ],
    )


def delete_account(session: Session, user: User, password: str) -> None:
    _confirm_password(user, password)
    removed = repository.delete_sole_owned_proposals(session, user.id)
    # Memberships and sessions cascade; authored versions and share links keep a null author.
    session.delete(user)
    session.commit()
    logger.info("account_deleted", extra={"proposals_deleted": removed})
