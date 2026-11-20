import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.features.auth.dependencies import CurrentUser
from app.features.proposals import repository, service
from app.features.proposals.models import ProposalRole
from app.features.proposals.schemas import (
    ProposalCreate,
    ProposalDetail,
    ProposalPage,
    ProposalSummary,
    ProposalUpdate,
    SearchQuery,
)
from app.shared.db import get_session

router = APIRouter(prefix="/proposals", tags=["proposals"])

DbSession = Annotated[Session, Depends(get_session)]


def _detail(session: Session, access: service.Access) -> ProposalDetail:
    return service.detail(session, access.proposal, access.role)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a proposal")
def create(body: ProposalCreate, user: CurrentUser, session: DbSession) -> ProposalDetail:
    return _detail(
        session, service.create(session, user.id, body.title, body.client_name, body.briefing)
    )


@router.get("", summary="List the proposals the current user can access")
def list_proposals(
    user: CurrentUser,
    session: DbSession,
    archived: bool = False,
    q: SearchQuery = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProposalPage:
    rows, total = repository.list_for_user(
        session, user.id, archived, q, limit, offset, datetime.now(UTC)
    )
    items = [
        ProposalSummary(
            id=proposal.id,
            title=proposal.title,
            client_name=proposal.client_name,
            role=role,
            status=proposal_status,
            archived_at=proposal.archived_at,
            updated_at=proposal.updated_at,
        )
        for proposal, role, proposal_status in rows
    ]
    return ProposalPage(items=items, total=total)


@router.get("/{proposal_id}", summary="Get a proposal")
def get(proposal_id: uuid.UUID, user: CurrentUser, session: DbSession) -> ProposalDetail:
    return _detail(session, service.authorize(session, proposal_id, user.id, ProposalRole.VIEWER))


@router.patch("/{proposal_id}", summary="Update proposal metadata")
def update(
    proposal_id: uuid.UUID, body: ProposalUpdate, user: CurrentUser, session: DbSession
) -> ProposalDetail:
    access = service.authorize(session, proposal_id, user.id, ProposalRole.EDITOR)
    return _detail(session, service.update(session, access, body.title, body.client_name))


@router.post("/{proposal_id}/archive", summary="Archive a proposal")
def archive(proposal_id: uuid.UUID, user: CurrentUser, session: DbSession) -> ProposalDetail:
    access = service.authorize(session, proposal_id, user.id, ProposalRole.OWNER)
    return _detail(session, service.set_archived(session, access, archived=True))


@router.post("/{proposal_id}/unarchive", summary="Restore an archived proposal")
def unarchive(proposal_id: uuid.UUID, user: CurrentUser, session: DbSession) -> ProposalDetail:
    access = service.authorize(session, proposal_id, user.id, ProposalRole.OWNER)
    return _detail(session, service.set_archived(session, access, archived=False))


@router.delete(
    "/{proposal_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a proposal"
)
def delete(proposal_id: uuid.UUID, user: CurrentUser, session: DbSession) -> None:
    service.delete(session, service.authorize(session, proposal_id, user.id, ProposalRole.OWNER))
