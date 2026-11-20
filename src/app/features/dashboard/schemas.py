import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from app.features.proposals.models import ProposalRole


class ProposalStatus(StrEnum):
    DRAFT = "draft"
    GENERATED = "generated"
    EDITED = "edited"
    SHARED = "shared"
    ARCHIVED = "archived"


class ActivityKind(StrEnum):
    GENERATED = "generated"
    EDITED = "edited"
    RESTORED = "restored"
    LINK_CREATED = "link_created"
    LINK_REVOKED = "link_revoked"


class RecentProposal(BaseModel):
    id: uuid.UUID
    title: str
    client_name: str
    role: ProposalRole
    status: ProposalStatus
    updated_at: datetime


class ActiveLink(BaseModel):
    id: uuid.UUID
    proposal_id: uuid.UUID
    proposal_title: str
    expires_at: datetime


class Activity(BaseModel):
    event_id: uuid.UUID
    kind: ActivityKind
    proposal_id: uuid.UUID
    proposal_title: str
    occurred_at: datetime
    version: int | None


class DashboardSummary(BaseModel):
    proposal_counts: dict[ProposalStatus, int]
    generations_last_30_days: int
    active_link_count: int
    expiring_link_count: int
    recent_proposals: list[RecentProposal]
    active_links: list[ActiveLink]
    recent_activity: list[Activity]
