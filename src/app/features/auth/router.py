from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlalchemy.orm import Session

from app.features.auth import service
from app.features.auth.dependencies import CurrentUser
from app.features.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.shared.config import get_settings
from app.shared.db import get_session
from app.shared.rate_limit import rate_limit

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/auth"

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[Session, Depends(get_session)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


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
def register(body: RegisterRequest, session: DbSession, response: Response) -> TokenResponse:
    return _respond(response, service.register(session, body.email, body.name, body.password))


@router.post(
    "/login",
    summary="Start a session",
    dependencies=[Depends(rate_limit("5/minute"))],
)
def login(body: LoginRequest, session: DbSession, response: Response) -> TokenResponse:
    return _respond(response, service.login(session, body.email, body.password))


@router.post(
    "/refresh",
    summary="Rotate the refresh token and issue a new access token",
    dependencies=[Depends(rate_limit("30/minute"))],
)
def refresh(
    session: DbSession, response: Response, refresh_token: RefreshCookie = None
) -> TokenResponse:
    return _respond(response, service.refresh(session, refresh_token))


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
