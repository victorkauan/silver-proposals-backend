import uuid
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy.orm import Session

from app.features.auth import repository, security, two_factor
from app.features.auth.models import User
from app.features.auth.service import check_second_factor, confirm_password
from app.features.security.schemas import SessionResponse, TwoFactorSetup, TwoFactorStatus
from app.shared.errors import AppError, ErrorCode


def two_factor_status(session: Session, user: User) -> TwoFactorStatus:
    return TwoFactorStatus(
        enabled=user.two_factor_enabled,
        enabled_at=user.totp_enabled_at,
        recovery_codes_remaining=repository.count_unused_recovery_codes(session, user.id),
    )


def start_setup(session: Session, user: User, password: str) -> TwoFactorSetup:
    confirm_password(user, password)
    if user.two_factor_enabled:
        raise AppError(ErrorCode.TWO_FACTOR_ALREADY_ENABLED, status.HTTP_409_CONFLICT)
    secret = two_factor.new_secret()
    user.totp_pending_secret = two_factor.encrypt_secret(user.id, secret)
    session.commit()
    return TwoFactorSetup(
        secret=secret, otpauth_uri=two_factor.provisioning_uri(secret, user.email)
    )


def _issue_recovery_codes(session: Session, user: User) -> list[str]:
    codes = two_factor.new_recovery_codes()
    repository.replace_recovery_codes(
        session, user.id, [two_factor.hash_recovery_code(code) for code in codes]
    )
    return codes


def enable(session: Session, user: User, code: str) -> list[str]:
    if user.two_factor_enabled:
        raise AppError(ErrorCode.TWO_FACTOR_ALREADY_ENABLED, status.HTTP_409_CONFLICT)
    if user.totp_pending_secret is None:
        raise AppError(ErrorCode.TWO_FACTOR_SETUP_REQUIRED, status.HTTP_409_CONFLICT)
    secret = two_factor.decrypt_secret(user.id, user.totp_pending_secret)
    step = two_factor.match_totp(secret, code.strip(), None)
    if step is None:
        raise AppError(ErrorCode.INVALID_TWO_FACTOR_CODE, status.HTTP_400_BAD_REQUEST)
    user.totp_secret = user.totp_pending_secret
    user.totp_pending_secret = None
    user.totp_last_step = step
    user.totp_enabled_at = datetime.now(UTC)
    codes = _issue_recovery_codes(session, user)
    session.commit()
    return codes


def _require_enabled(user: User) -> None:
    if not user.two_factor_enabled:
        raise AppError(ErrorCode.TWO_FACTOR_NOT_ENABLED, status.HTTP_409_CONFLICT)


def disable(session: Session, user: User, password: str, code: str) -> None:
    confirm_password(user, password)
    _require_enabled(user)
    if not check_second_factor(session, user, code):
        session.commit()
        raise AppError(ErrorCode.INVALID_TWO_FACTOR_CODE, status.HTTP_400_BAD_REQUEST)
    user.totp_secret = None
    user.totp_pending_secret = None
    user.totp_last_step = None
    user.totp_enabled_at = None
    repository.delete_recovery_codes(session, user.id)
    session.commit()


def regenerate_recovery_codes(session: Session, user: User, password: str) -> list[str]:
    confirm_password(user, password)
    _require_enabled(user)
    codes = _issue_recovery_codes(session, user)
    session.commit()
    return codes


def change_password(
    session: Session, user: User, session_id: uuid.UUID, current: str, new: str
) -> int:
    confirm_password(user, current)
    user.password_hash = security.hash_password(new)
    # A new password should lock out whoever may have used the old one elsewhere.
    revoked = repository.revoke_user_sessions(
        session, user.id, datetime.now(UTC), keep_family_id=session_id
    )
    session.commit()
    return revoked


def list_sessions(session: Session, user: User, session_id: uuid.UUID) -> list[SessionResponse]:
    return [
        SessionResponse(
            id=token.family_id,
            started_at=token.session_started_at,
            last_active_at=token.created_at,
            expires_at=token.expires_at,
            user_agent=token.user_agent,
            current=token.family_id == session_id,
        )
        for token in repository.active_sessions(session, user.id, datetime.now(UTC))
    ]


def end_session(session: Session, user: User, family_id: uuid.UUID) -> None:
    if not repository.revoke_user_sessions(session, user.id, datetime.now(UTC), family_id):
        raise AppError(ErrorCode.SESSION_NOT_FOUND, status.HTTP_404_NOT_FOUND)
    session.commit()


def end_other_sessions(session: Session, user: User, session_id: uuid.UUID) -> int:
    revoked = repository.revoke_user_sessions(
        session, user.id, datetime.now(UTC), keep_family_id=session_id
    )
    session.commit()
    return revoked
