import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, delete, exists, func, select, update
from sqlalchemy.orm import Session

from app.features.auth.models import RecoveryCode, RefreshToken, User


def get_user_by_email(session: Session, email: str, *, lock: bool = False) -> User | None:
    query = select(User).where(User.email == email)
    return session.scalar(query.with_for_update() if lock else query)


def get_user(session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


def lock_user(session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id, populate_existing=True, with_for_update=True)


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
    session_started_at: datetime,
    user_agent: str | None,
) -> RefreshToken:
    token = RefreshToken(
        user_id=user_id,
        family_id=family_id,
        token_hash=token_hash,
        expires_at=expires_at,
        session_started_at=session_started_at,
        user_agent=user_agent,
    )
    session.add(token)
    return token


def session_is_active(
    session: Session, user_id: uuid.UUID, family_id: uuid.UUID, now: datetime
) -> bool:
    return bool(
        session.scalar(
            select(
                exists().where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.family_id == family_id,
                    RefreshToken.used_at.is_(None),
                    RefreshToken.revoked_at.is_(None),
                    RefreshToken.expires_at > now,
                )
            )
        )
    )


def active_sessions(session: Session, user_id: uuid.UUID, now: datetime) -> list[RefreshToken]:
    # Each live session has exactly one unrotated token: the head of its family.
    return list(
        session.scalars(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.used_at.is_(None),
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
            .order_by(RefreshToken.created_at.desc())
        ).all()
    )


def revoke_user_sessions(
    session: Session,
    user_id: uuid.UUID,
    now: datetime,
    family_id: uuid.UUID | None = None,
    keep_family_id: uuid.UUID | None = None,
) -> int:
    families = [
        token.family_id
        for token in active_sessions(session, user_id, now)
        if (family_id is None or token.family_id == family_id) and token.family_id != keep_family_id
    ]
    if families:
        session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.family_id.in_(families),
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
    return len(families)


def replace_recovery_codes(session: Session, user_id: uuid.UUID, code_hashes: list[str]) -> None:
    delete_recovery_codes(session, user_id)
    session.add_all(RecoveryCode(user_id=user_id, code_hash=code) for code in code_hashes)


def delete_recovery_codes(session: Session, user_id: uuid.UUID) -> None:
    session.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user_id))


def get_unused_recovery_code_for_update(
    session: Session, user_id: uuid.UUID, code_hash: str
) -> RecoveryCode | None:
    return session.scalar(
        select(RecoveryCode)
        .where(
            RecoveryCode.user_id == user_id,
            RecoveryCode.code_hash == code_hash,
            RecoveryCode.used_at.is_(None),
        )
        .with_for_update()
    )


def count_unused_recovery_codes(session: Session, user_id: uuid.UUID) -> int:
    count = session.scalar(
        select(func.count())
        .select_from(RecoveryCode)
        .where(RecoveryCode.user_id == user_id, RecoveryCode.used_at.is_(None))
    )
    return count or 0


def refresh_token_owner(session: Session, token_hash: str) -> uuid.UUID | None:
    return session.scalar(select(RefreshToken.user_id).where(RefreshToken.token_hash == token_hash))


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
