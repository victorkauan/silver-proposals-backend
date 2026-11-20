import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.features.auth.dependencies import CurrentAuth, CurrentUser, LockedAuth, LockedUser
from app.features.security import service
from app.features.security.schemas import (
    PasswordChange,
    RecoveryCodes,
    RecoveryCodesRequest,
    SessionResponse,
    SessionsRevoked,
    TwoFactorDisableRequest,
    TwoFactorEnableRequest,
    TwoFactorSetup,
    TwoFactorSetupRequest,
    TwoFactorStatus,
)
from app.shared.db import get_session
from app.shared.rate_limit import rate_limit

router = APIRouter(prefix="/account", tags=["security"])

DbSession = Annotated[Session, Depends(get_session)]
Limited = [Depends(rate_limit("5/minute"))]


@router.get("/two-factor", summary="Two-factor authentication status")
def two_factor_status(user: CurrentUser, session: DbSession) -> TwoFactorStatus:
    return service.two_factor_status(session, user)


@router.post(
    "/two-factor/setup",
    summary="Start the authenticator setup (requires the password)",
    dependencies=Limited,
)
def start_setup(
    body: TwoFactorSetupRequest, user: LockedUser, session: DbSession
) -> TwoFactorSetup:
    return service.start_setup(session, user, body.password)


@router.post(
    "/two-factor/enable",
    summary="Confirm the first code, enable 2FA, and return the recovery codes",
    dependencies=Limited,
)
def enable(body: TwoFactorEnableRequest, user: LockedUser, session: DbSession) -> RecoveryCodes:
    return RecoveryCodes(codes=service.enable(session, user, body.code))


@router.post(
    "/two-factor/disable",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disable 2FA (requires the password and a code)",
    dependencies=Limited,
)
def disable(body: TwoFactorDisableRequest, user: LockedUser, session: DbSession) -> None:
    service.disable(session, user, body.password, body.code)


@router.post(
    "/two-factor/recovery-codes",
    summary="Replace the recovery codes (requires the password)",
    dependencies=Limited,
)
def regenerate_recovery_codes(
    body: RecoveryCodesRequest, user: LockedUser, session: DbSession
) -> RecoveryCodes:
    return RecoveryCodes(codes=service.regenerate_recovery_codes(session, user, body.password))


@router.put(
    "/password",
    summary="Change the password and end every other session",
    dependencies=Limited,
)
def change_password(body: PasswordChange, auth: LockedAuth, session: DbSession) -> SessionsRevoked:
    revoked = service.change_password(
        session, auth.user, auth.session_id, body.current_password, body.new_password
    )
    return SessionsRevoked(revoked=revoked)


@router.get("/sessions", summary="Active sessions")
def list_sessions(auth: CurrentAuth, session: DbSession) -> list[SessionResponse]:
    return service.list_sessions(session, auth.user, auth.session_id)


@router.post("/sessions/revoke-others", summary="End every session except the current one")
def end_other_sessions(auth: LockedAuth, session: DbSession) -> SessionsRevoked:
    return SessionsRevoked(revoked=service.end_other_sessions(session, auth.user, auth.session_id))


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="End one session",
)
def end_session(session_id: uuid.UUID, user: LockedUser, session: DbSession) -> None:
    service.end_session(session, user, session_id)
