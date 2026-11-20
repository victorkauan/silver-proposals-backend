from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, Response, status
from sqlalchemy.orm import Session

from app.features.auth import security, service
from app.features.auth.dependencies import CurrentUser
from app.features.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    TwoFactorChallengeResponse,
    TwoFactorLoginRequest,
    UserResponse,
)
from app.shared.config import get_settings
from app.shared.db import get_session
from app.shared.rate_limit import rate_limit

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/auth"

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[Session, Depends(get_session)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]
UserAgent = Annotated[str | None, Header()]


def _respond(response: Response, result: service.AuthSession) -> TokenResponse:
    settings = get_settings()
    # httpOnly keeps the long-lived token away from JavaScript (XSS); SameSite=Strict blocks CSRF.
    response.set_cookie(
        REFRESH_COOKIE,
        result.refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite="strict",
    )
    return TokenResponse(
        access_token=result.access_token,
        expires_in=settings.access_token_ttl_minutes * 60,
        user=UserResponse.model_validate(result.user),
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Create an account and start a session",
    dependencies=[Depends(rate_limit("3/minute"))],
)
def register(
    body: RegisterRequest, session: DbSession, response: Response, user_agent: UserAgent = None
) -> TokenResponse:
    return _respond(
        response, service.register(session, body.email, body.name, body.password, user_agent)
    )


@router.post(
    "/login",
    summary="Start a session",
    dependencies=[Depends(rate_limit("5/minute"))],
)
def login(
    body: LoginRequest, session: DbSession, response: Response, user_agent: UserAgent = None
) -> TokenResponse | TwoFactorChallengeResponse:
    result = service.login(session, body.email, body.password, user_agent)
    if isinstance(result, service.TwoFactorChallenge):
        return TwoFactorChallengeResponse(
            challenge_token=result.challenge_token,
            expires_in=int(security.CHALLENGE_TTL.total_seconds()),
        )
    return _respond(response, result)


@router.post(
    "/login/two-factor",
    summary="Finish a login with an authenticator or recovery code",
    dependencies=[Depends(rate_limit("5/minute"))],
)
def login_two_factor(
    body: TwoFactorLoginRequest,
    session: DbSession,
    response: Response,
    user_agent: UserAgent = None,
) -> TokenResponse:
    return _respond(
        response,
        service.complete_two_factor(session, body.challenge_token, body.code, user_agent),
    )


@router.post(
    "/refresh",
    summary="Rotate the refresh token and issue a new access token",
    dependencies=[Depends(rate_limit("30/minute"))],
)
def refresh(
    session: DbSession,
    response: Response,
    refresh_token: RefreshCookie = None,
    user_agent: UserAgent = None,
) -> TokenResponse:
    return _respond(response, service.refresh(session, refresh_token, user_agent))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="End the session",
)
def logout(session: DbSession, response: Response, refresh_token: RefreshCookie = None) -> None:
    service.logout(session, refresh_token)
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, secure=True, httponly=True, samesite="strict"
    )


@router.get("/me", summary="Current user")
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
