import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.features.proposals.models import Proposal, ProposalRole
from app.features.proposals.status import ProposalStatus

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Briefing = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10_000)]


class ProposalCreate(BaseModel):
    title: Title
    client_name: Title
    briefing: Briefing = ""


class ProposalUpdate(BaseModel):
    title: Title | None = None
    client_name: Title | None = None


class ProposalSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    client_name: str
    role: ProposalRole
    status: ProposalStatus
    archived_at: datetime | None
    updated_at: datetime


class ProposalDetail(ProposalSummary):
    briefing: str
    content: str
    version: int
    created_at: datetime


SearchQuery = Annotated[
    str | None,
    StringConstraints(strip_whitespace=True, max_length=200),
]


class ProposalPage(BaseModel):
    items: list[ProposalSummary]
    total: int


def to_detail(proposal: Proposal, role: ProposalRole, status: ProposalStatus) -> ProposalDetail:
    return ProposalDetail(
        id=proposal.id,
        title=proposal.title,
        client_name=proposal.client_name,
        role=role,
        status=status,
        archived_at=proposal.archived_at,
        updated_at=proposal.updated_at,
        briefing=proposal.briefing,
        content=proposal.content,
        version=proposal.version,
        created_at=proposal.created_at,
    )
