from datetime import datetime
from enum import StrEnum

from sqlalchemy import ColumnElement, and_, case, select

from app.features.proposals.models import Proposal, ProposalVersion, VersionSource
from app.features.sharing.models import ShareLink


class ProposalStatus(StrEnum):
    DRAFT = "draft"
    GENERATED = "generated"
    EDITED = "edited"
    SHARED = "shared"
    ARCHIVED = "archived"


def status_expression(is_owner: ColumnElement[bool], now: datetime) -> ColumnElement[str]:
    # Only owners see share links, so "shared" is never revealed to editors or viewers.
    has_active_link = (
        select(ShareLink.id)
        .where(
            ShareLink.proposal_id == Proposal.id,
            ShareLink.revoked_at.is_(None),
            ShareLink.expires_at > now,
        )
        .exists()
    )
    current_source = (
        select(ProposalVersion.source)
        .where(
            ProposalVersion.proposal_id == Proposal.id,
            ProposalVersion.number == Proposal.version,
        )
        .scalar_subquery()
    )
    return case(
        (Proposal.archived_at.is_not(None), ProposalStatus.ARCHIVED.value),
        (and_(is_owner, has_active_link), ProposalStatus.SHARED.value),
        (current_source == VersionSource.GENERATED, ProposalStatus.GENERATED.value),
        (Proposal.version > 0, ProposalStatus.EDITED.value),
        else_=ProposalStatus.DRAFT.value,
    )
