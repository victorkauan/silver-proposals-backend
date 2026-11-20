import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.features.auth import repository, security
from app.features.auth.models import User
from app.shared.db import get_session
from app.shared.errors import AppError, ErrorCode

bearer = HTTPBearer(auto_error=False)
CHALLENGE = {"WWW-Authenticate": "Bearer"}


@dataclass(frozen=True)
class Authenticated:
    user: User
    session_id: uuid.UUID


def get_authenticated(
    session: Annotated[Session, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Authenticated:
    if credentials is None:
        raise AppError(ErrorCode.NOT_AUTHENTICATED, status.HTTP_401_UNAUTHORIZED, CHALLENGE)
    invalid = AppError(ErrorCode.INVALID_TOKEN, status.HTTP_401_UNAUTHORIZED, CHALLENGE)
    claims = security.decode_access_token(credentials.credentials)
    if claims is None:
        raise invalid
    # Checked on every request so that ending a session takes effect at once, not at token expiry.
    if not repository.session_is_active(
        session, claims.user_id, claims.session_id, datetime.now(UTC)
    ):
        raise invalid
    user = repository.get_user(session, claims.user_id)
    if user is None:
        raise invalid
    return Authenticated(user, claims.session_id)


def get_current_user(auth: Annotated[Authenticated, Depends(get_authenticated)]) -> User:
    return auth.user


CurrentAuth = Annotated[Authenticated, Depends(get_authenticated)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def lock_authenticated(
    auth: CurrentAuth, session: Annotated[Session, Depends(get_session)]
) -> Authenticated:
    user = repository.lock_user(session, auth.user.id)
    if user is None or not repository.session_is_active(
        session, user.id, auth.session_id, datetime.now(UTC)
    ):
        raise AppError(ErrorCode.INVALID_TOKEN, status.HTTP_401_UNAUTHORIZED, CHALLENGE)
    return Authenticated(user, auth.session_id)


def lock_current_user(auth: Annotated[Authenticated, Depends(lock_authenticated)]) -> User:
    return auth.user


LockedAuth = Annotated[Authenticated, Depends(lock_authenticated)]
LockedUser = Annotated[User, Depends(lock_current_user)]
