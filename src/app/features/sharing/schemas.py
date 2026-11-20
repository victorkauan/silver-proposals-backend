import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


class ShareLinkCreate(BaseModel):
    expires_in_days: Annotated[int, Field(ge=1, le=90)] = 7


class ShareLinkSummary(BaseModel):
    id: uuid.UUID
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime
    active: bool


class ShareLinkCreated(ShareLinkSummary):
    token: str


class ShareLinkResolve(BaseModel):
    token: str


class SharedProposal(BaseModel):
    title: str
    client_name: str
    content: str
    updated_at: datetime
