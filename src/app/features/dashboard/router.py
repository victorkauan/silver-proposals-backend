from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.features.auth.dependencies import CurrentUser
from app.features.dashboard import repository
from app.features.dashboard.schemas import DashboardSummary
from app.shared.db import get_session

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", summary="Get the current user's dashboard")
def get_summary(
    user: CurrentUser, session: Annotated[Session, Depends(get_session)], response: Response
) -> DashboardSummary:
    response.headers["Cache-Control"] = "no-store"
    return repository.summary(session, user.id, datetime.now(UTC))
