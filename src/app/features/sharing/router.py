import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.features.auth.dependencies import CurrentUser
from app.features.proposals import service as proposals
from app.features.proposals.models import ProposalRole
from app.features.sharing import service
from app.features.sharing.models import ShareLink
from app.features.sharing.schemas import (
    SharedProposal,
    ShareLinkCreate,
    ShareLinkCreated,
    ShareLinkSummary,
)
from app.shared.db import get_session
from app.shared.rate_limit import rate_limit

router = APIRouter(tags=["sharing"])

DbSession = Annotated[Session, Depends(get_session)]


def _summary(link: ShareLink) -> ShareLinkSummary:
    return ShareLinkSummary(
        id=link.id,
        expires_at=link.expires_at,
        revoked_at=link.revoked_at,
        created_at=link.created_at,
        active=service.is_active(link, datetime.now(UTC)),
    )


@router.post(
    "/proposals/{proposal_id}/share-links",
    status_code=status.HTTP_201_CREATED,
    summary="Create a public share link (the token is shown only once)",
)
def create(
    proposal_id: uuid.UUID, body: ShareLinkCreate, user: CurrentUser, session: DbSession
) -> ShareLinkCreated:
    proposals.authorize(session, proposal_id, user.id, ProposalRole.OWNER)
    link, token = service.create(session, proposal_id, user.id, body.expires_in_days)
    return ShareLinkCreated(**_summary(link).model_dump(), token=token)


@router.get("/proposals/{proposal_id}/share-links", summary="List share links")
def list_links(
    proposal_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> list[ShareLinkSummary]:
    proposals.authorize(session, proposal_id, user.id, ProposalRole.OWNER)
    return [_summary(link) for link in service.list_links(session, proposal_id)]


@router.delete(
    "/proposals/{proposal_id}/share-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a share link",
)
def revoke(
    proposal_id: uuid.UUID, link_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> None:
    proposals.authorize(session, proposal_id, user.id, ProposalRole.OWNER)
    service.revoke(session, proposal_id, link_id)


@router.get(
    "/public/proposals/{token}",
    summary="Read a shared proposal without logging in",
    dependencies=[Depends(rate_limit("60/minute"))],
)
def read_shared(token: str, session: DbSession, response: Response) -> SharedProposal:
    proposal = service.resolve(session, token)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    return SharedProposal(
        title=proposal.title,
        client_name=proposal.client_name,
        content=proposal.content,
        updated_at=proposal.updated_at,
    )
