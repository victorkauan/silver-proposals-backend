import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.features.proposals.models import ProposalRole

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
    archived_at: datetime | None
    updated_at: datetime


class ProposalDetail(ProposalSummary):
    briefing: str
    content: str
    created_at: datetime


class ProposalPage(BaseModel):
    items: list[ProposalSummary]
    total: int
