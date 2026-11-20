import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.orm import Session

from app.features.auth.models import RefreshToken, User


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email))


def get_user(session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


def add_user(session: Session, email: str, name: str, password_hash: str) -> User:
    user = User(email=email, name=name, password_hash=password_hash)
    session.add(user)
    session.flush()
    return user


def add_refresh_token(
    session: Session,
    user_id: uuid.UUID,
    family_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
) -> RefreshToken:
    token = RefreshToken(
        user_id=user_id, family_id=family_id, token_hash=token_hash, expires_at=expires_at
    )
    session.add(token)
    return token


def get_refresh_token_for_update(session: Session, token_hash: str) -> RefreshToken | None:
    return session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    )


def revoke_family(session: Session, family_id: uuid.UUID, now: datetime) -> None:
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def delete_expired_refresh_tokens(session: Session, now: datetime) -> int:
    # Revoked and rotated tokens stay until they expire: reuse detection needs them until then.
    result = session.execute(delete(RefreshToken).where(RefreshToken.expires_at <= now))
    return cast(CursorResult[tuple[()]], result).rowcount
