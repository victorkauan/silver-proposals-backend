import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.features.auth.dependencies import CurrentUser
from app.features.proposals import service as proposals
from app.features.proposals.models import ProposalRole, ProposalVersion
from app.features.proposals.schemas import ProposalDetail
from app.features.versions import repository, service
from app.features.versions.schemas import ContentUpdate, VersionDetail, VersionPage, VersionSummary
from app.shared.db import get_session

router = APIRouter(prefix="/proposals/{proposal_id}", tags=["versions"])

DbSession = Annotated[Session, Depends(get_session)]


def _summary(version: ProposalVersion, author_name: str | None) -> VersionSummary:
    return VersionSummary(
        number=version.number,
        source=version.source,
        author_name=author_name,
        content_chars=len(version.content),
        created_at=version.created_at,
    )


@router.put("/content", summary="Save the proposal content as a new version")
def save_content(
    proposal_id: uuid.UUID, body: ContentUpdate, user: CurrentUser, session: DbSession
) -> ProposalDetail:
    access = proposals.authorize(session, proposal_id, user.id, ProposalRole.EDITOR)
    proposal = service.save_content(session, proposal_id, body.content, body.base_version, user.id)
    return proposals.detail(session, proposal, access.role)


@router.get("/versions", summary="List the version history, newest first")
def list_versions(
    proposal_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> VersionPage:
    proposals.authorize(session, proposal_id, user.id, ProposalRole.VIEWER)
    rows, total = repository.list_versions(session, proposal_id, limit, offset)
    return VersionPage(items=[_summary(version, name) for version, name in rows], total=total)


@router.get("/versions/{number}", summary="Get one version")
def get_version(
    proposal_id: uuid.UUID, number: int, user: CurrentUser, session: DbSession
) -> VersionDetail:
    proposals.authorize(session, proposal_id, user.id, ProposalRole.VIEWER)
    version, author_name = service.get_version(session, proposal_id, number)
    return VersionDetail(**_summary(version, author_name).model_dump(), content=version.content)


@router.post("/versions/{number}/restore", summary="Restore a version as a new version")
def restore(
    proposal_id: uuid.UUID, number: int, user: CurrentUser, session: DbSession
) -> ProposalDetail:
    access = proposals.authorize(session, proposal_id, user.id, ProposalRole.EDITOR)
    proposal = service.restore(session, proposal_id, number, user.id)
    return proposals.detail(session, proposal, access.role)
