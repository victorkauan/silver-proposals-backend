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


def get_current_user(
    session: Annotated[Session, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise AppError(ErrorCode.NOT_AUTHENTICATED, status.HTTP_401_UNAUTHORIZED, CHALLENGE)
    user_id = security.decode_access_token(credentials.credentials)
    user = repository.get_user(session, user_id) if user_id else None
    if user is None:
        raise AppError(ErrorCode.INVALID_TOKEN, status.HTTP_401_UNAUTHORIZED, CHALLENGE)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
