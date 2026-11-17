import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy.orm import Session

from app.features.auth import repository, security
from app.features.auth.models import User
from app.shared.config import get_settings
from app.shared.errors import AppError, ErrorCode


@dataclass(frozen=True)
class AuthSession:
    user: User
    access_token: str
    refresh_token: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _start_session(session: Session, user: User, family_id: uuid.UUID | None = None) -> AuthSession:
    now = datetime.now(UTC)
    refresh_token = security.new_refresh_token()
    repository.add_refresh_token(
        session,
        user_id=user.id,
        family_id=family_id or uuid.uuid4(),
        token_hash=security.hash_refresh_token(refresh_token),
        expires_at=now + timedelta(days=get_settings().refresh_token_ttl_days),
    )
    return AuthSession(user, security.create_access_token(user.id, now), refresh_token)


def register(session: Session, email: str, name: str, password: str) -> AuthSession:
    email = normalize_email(email)
    if repository.get_user_by_email(session, email) is not None:
        raise AppError(ErrorCode.EMAIL_TAKEN, status.HTTP_409_CONFLICT)
    user = repository.add_user(session, email, name, security.hash_password(password))
    result = _start_session(session, user)
    session.commit()
    return result


def login(session: Session, email: str, password: str) -> AuthSession:
    user = repository.get_user_by_email(session, normalize_email(email))
    if user is None:
        security.burn_password_check(password)
        raise AppError(ErrorCode.INVALID_CREDENTIALS, status.HTTP_401_UNAUTHORIZED)
    if not security.verify_password(user.password_hash, password):
        raise AppError(ErrorCode.INVALID_CREDENTIALS, status.HTTP_401_UNAUTHORIZED)
    if security.password_needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(password)
    result = _start_session(session, user)
    session.commit()
    return result


def refresh(session: Session, refresh_token: str | None) -> AuthSession:
    invalid = AppError(ErrorCode.INVALID_REFRESH_TOKEN, status.HTTP_401_UNAUTHORIZED)
    if not refresh_token:
        raise invalid
    now = datetime.now(UTC)
    stored = repository.get_refresh_token_for_update(
        session, security.hash_refresh_token(refresh_token)
    )
    if stored is None or stored.revoked_at is not None or stored.expires_at <= now:
        raise invalid
    if stored.used_at is not None:
        # A rotated token presented again means it leaked: end every session of this family.
        repository.revoke_family(session, stored.family_id, now)
        session.commit()
        raise invalid
    user = repository.get_user(session, stored.user_id)
    if user is None:
        raise invalid
    stored.used_at = now
    result = _start_session(session, user, stored.family_id)
    session.commit()
    return result


def logout(session: Session, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    stored = repository.get_refresh_token_for_update(
        session, security.hash_refresh_token(refresh_token)
    )
    if stored is not None:
        repository.revoke_family(session, stored.family_id, datetime.now(UTC))
        session.commit()
