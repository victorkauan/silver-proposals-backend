import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field

from app.features.auth.schemas import Name
from app.features.proposals.models import ProposalRole, VersionSource

ConfirmPassword = Annotated[str, Field(min_length=1, max_length=128)]


class ProfileUpdate(BaseModel):
    name: Name


class EmailChange(BaseModel):
    email: EmailStr
    password: ConfirmPassword


class AccountDeletion(BaseModel):
    password: ConfirmPassword


class ExportedAccount(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    created_at: datetime
    updated_at: datetime
    privacy_version: str | None
    privacy_accepted_at: datetime | None


class ExportedSession(BaseModel):
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None


class ExportedProposal(BaseModel):
    id: uuid.UUID
    role: ProposalRole
    title: str
    client_name: str
    briefing: str
    content: str
    version: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExportedVersion(BaseModel):
    proposal_id: uuid.UUID
    number: int
    source: VersionSource
    content: str
    created_at: datetime


class ExportedShareLink(BaseModel):
    proposal_id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class AccountExport(BaseModel):
    exported_at: datetime
    account: ExportedAccount
    sessions: list[ExportedSession]
    proposals: list[ExportedProposal]
    authored_versions: list[ExportedVersion]
    share_links_created: list[ExportedShareLink]
