from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.features.account import service
from app.features.account.schemas import (
    AccountDeletion,
    AccountExport,
    EmailChange,
    ProfileUpdate,
)
from app.features.auth.dependencies import CurrentUser
from app.features.auth.router import REFRESH_COOKIE, REFRESH_COOKIE_PATH
from app.features.auth.schemas import UserResponse
from app.shared.db import get_session
from app.shared.rate_limit import rate_limit

router = APIRouter(prefix="/account", tags=["account"])

DbSession = Annotated[Session, Depends(get_session)]


@router.patch("", summary="Update the profile")
def update_profile(body: ProfileUpdate, user: CurrentUser, session: DbSession) -> UserResponse:
    return UserResponse.model_validate(service.update_profile(session, user, body.name))


@router.put(
    "/email",
    summary="Change the e-mail (requires the password)",
    dependencies=[Depends(rate_limit("5/minute"))],
)
def change_email(body: EmailChange, user: CurrentUser, session: DbSession) -> UserResponse:
    return UserResponse.model_validate(
        service.change_email(session, user, body.email, body.password)
    )


@router.post("/privacy-acceptance", summary="Accept the current privacy notice")
def accept_privacy(user: CurrentUser, session: DbSession) -> UserResponse:
    return UserResponse.model_validate(service.accept_current_privacy_notice(session, user))


@router.get(
    "/export",
    summary="Export the user's personal data (LGPD art. 18)",
    response_model=AccountExport,
    dependencies=[Depends(rate_limit("3/minute"))],
)
def export(user: CurrentUser, session: DbSession) -> JSONResponse:
    data = service.export(session, user)
    return JSONResponse(
        content=data.model_dump(mode="json"),
        headers={
            "Content-Disposition": 'attachment; filename="silver-proposals-dados.json"',
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete the account (requires the password)",
    dependencies=[Depends(rate_limit("3/minute"))],
)
def delete_account(
    body: AccountDeletion, user: CurrentUser, session: DbSession, response: Response
) -> None:
    service.delete_account(session, user, body.password)
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, secure=True, httponly=True, samesite="strict"
    )
