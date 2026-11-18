from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.features.proposals.models import VersionSource


class ContentUpdate(BaseModel):
    content: Annotated[str, Field(max_length=200_000)]
    base_version: Annotated[int, Field(ge=0)]


class VersionSummary(BaseModel):
    number: int
    source: VersionSource
    author_name: str | None
    content_chars: int
    created_at: datetime


class VersionDetail(VersionSummary):
    content: str


class VersionPage(BaseModel):
    items: list[VersionSummary]
    total: int
