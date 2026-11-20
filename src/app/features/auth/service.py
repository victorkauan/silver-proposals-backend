import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy.orm import Session

from app.features.auth import repository, security, two_factor
from app.features.auth.models import PRIVACY_NOTICE_VERSION, User
from app.shared.config import get_settings
from app.shared.errors import AppError, ErrorCode
from app.shared.rate_limit import hit_user_limit

USER_AGENT_MAX = 255


@dataclass(frozen=True)
class TwoFactorChallenge:
    challenge_token: str


@dataclass(frozen=True)
class AuthSession:
    user: User
    access_token: str
    refresh_token: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _start_session(
    session: Session,
    user: User,
    user_agent: str | None,
    family_id: uuid.UUID | None = None,
    started_at: datetime | None = None,
) -> AuthSession:
    now = datetime.now(UTC)
    family_id = family_id or uuid.uuid4()
    refresh_token = security.new_refresh_token()
    repository.add_refresh_token(
        session,
        user_id=user.id,
        family_id=family_id,
        token_hash=security.hash_refresh_token(refresh_token),
        expires_at=now + timedelta(days=get_settings().refresh_token_ttl_days),
        session_started_at=started_at or now,
        user_agent=user_agent[:USER_AGENT_MAX] if user_agent else None,
    )
    return AuthSession(user, security.create_access_token(user.id, family_id, now), refresh_token)


def register(
    session: Session, email: str, name: str, password: str, user_agent: str | None
) -> AuthSession:
    email = normalize_email(email)
    if repository.get_user_by_email(session, email) is not None:
        raise AppError(ErrorCode.EMAIL_TAKEN, status.HTTP_409_CONFLICT)
    user = repository.add_user(session, email, name, security.hash_password(password))
    accept_privacy(user)
    result = _start_session(session, user, user_agent)
    session.commit()
    return result


def login(
    session: Session, email: str, password: str, user_agent: str | None
) -> AuthSession | TwoFactorChallenge:
    user = repository.get_user_by_email(session, normalize_email(email), lock=True)
    if user is None:
        security.burn_password_check(password)
        raise AppError(ErrorCode.INVALID_CREDENTIALS, status.HTTP_401_UNAUTHORIZED)
    if not security.verify_password(user.password_hash, password):
        raise AppError(ErrorCode.INVALID_CREDENTIALS, status.HTTP_401_UNAUTHORIZED)
    if security.password_needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(password)
    if user.totp_secret is not None:
        credentials = security.challenge_credentials(user.password_hash, user.totp_secret)
        challenge = security.create_challenge_token(user.id, credentials)
        session.commit()
        return TwoFactorChallenge(challenge)
    result = _start_session(session, user, user_agent)
    session.commit()
    return result


def check_second_factor(session: Session, user: User, code: str) -> bool:
    if user.totp_secret is None:
        return False
    code = code.strip()
    if two_factor.is_totp_code(code):
        secret = two_factor.decrypt_secret(user.id, user.totp_secret)
        step = two_factor.match_totp(secret, code, user.totp_last_step)
        if step is None:
            return False
        user.totp_last_step = step
        return True
    stored = repository.get_unused_recovery_code_for_update(
        session, user.id, two_factor.hash_recovery_code(code)
    )
    if stored is None:
        return False
    stored.used_at = datetime.now(UTC)
    return True


def complete_two_factor(
    session: Session, challenge_token: str, code: str, user_agent: str | None
) -> AuthSession:
    invalid = AppError(ErrorCode.INVALID_CHALLENGE, status.HTTP_401_UNAUTHORIZED)
    claims = security.decode_challenge_token(challenge_token)
    if claims is None:
        raise invalid
    user = repository.lock_user(session, claims.user_id)
    if user is None or user.totp_secret is None:
        raise invalid
    credentials = security.challenge_credentials(user.password_hash, user.totp_secret)
    if not hmac.compare_digest(claims.credentials, credentials):
        raise invalid
    # Per account as well as per IP, so that spreading guesses over many addresses does not help.
    if not hit_user_limit("two_factor_login", user.id):
        raise AppError(ErrorCode.RATE_LIMITED, status.HTTP_429_TOO_MANY_REQUESTS)
    if not check_second_factor(session, user, code):
        session.commit()
        raise AppError(ErrorCode.INVALID_TWO_FACTOR_CODE, status.HTTP_401_UNAUTHORIZED)
    result = _start_session(session, user, user_agent)
    session.commit()
    return result


def refresh(session: Session, refresh_token: str | None, user_agent: str | None) -> AuthSession:
    invalid = AppError(ErrorCode.INVALID_REFRESH_TOKEN, status.HTTP_401_UNAUTHORIZED)
    if not refresh_token:
        raise invalid
    now = datetime.now(UTC)
    token_hash = security.hash_refresh_token(refresh_token)
    user_id = repository.refresh_token_owner(session, token_hash)
    # Session writers lock the user before operating on any token in their families.
    user = repository.lock_user(session, user_id) if user_id else None
    if user is None:
        raise invalid
    stored = repository.get_refresh_token_for_update(session, token_hash)
    if stored is None or stored.revoked_at is not None or stored.expires_at <= now:
        raise invalid
    if stored.used_at is not None:
        # A rotated token presented again means it leaked: end every session of this family.
        repository.revoke_family(session, stored.family_id, now)
        session.commit()
        raise invalid
    stored.used_at = now
    result = _start_session(session, user, user_agent, stored.family_id, stored.session_started_at)
    session.commit()
    return result


def confirm_password(user: User, password: str) -> None:
    if not security.verify_password(user.password_hash, password):
        raise AppError(ErrorCode.INVALID_PASSWORD, status.HTTP_403_FORBIDDEN)


def accept_privacy(user: User) -> None:
    user.privacy_version = PRIVACY_NOTICE_VERSION
    user.privacy_accepted_at = datetime.now(UTC)


def purge_refresh_tokens(session: Session) -> int:
    removed = repository.delete_expired_refresh_tokens(session, datetime.now(UTC))
    session.commit()
    return removed


def logout(session: Session, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    token_hash = security.hash_refresh_token(refresh_token)
    user_id = repository.refresh_token_owner(session, token_hash)
    if user_id is None or repository.lock_user(session, user_id) is None:
        return
    stored = repository.get_refresh_token_for_update(session, token_hash)
    if stored is not None:
        repository.revoke_family(session, stored.family_id, datetime.now(UTC))
        session.commit()
