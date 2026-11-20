import uuid
from datetime import datetime, timedelta

from sqlalchemy import Integer, String, and_, cast, func, literal, select, union_all
from sqlalchemy.orm import Session

from app.features.dashboard.schemas import (
    ActiveLink,
    Activity,
    ActivityKind,
    DashboardSummary,
    RecentProposal,
)
from app.features.proposals.models import (
    Proposal,
    ProposalMember,
    ProposalRole,
    ProposalVersion,
    VersionSource,
)
from app.features.proposals.status import ProposalStatus, status_expression
from app.features.sharing.models import ShareLink

PROPOSAL_LIMIT = 5
LINK_LIMIT = 5
ACTIVITY_LIMIT = 8


def summary(session: Session, user_id: uuid.UUID, now: datetime) -> DashboardSummary:
    membership = and_(ProposalMember.proposal_id == Proposal.id, ProposalMember.user_id == user_id)
    is_owner = ProposalMember.role == ProposalRole.OWNER
    is_active_link = and_(ShareLink.revoked_at.is_(None), ShareLink.expires_at > now)
    proposal_status = status_expression(is_owner, now).label("status")
    visible = (
        select(
            Proposal.id,
            Proposal.title,
            Proposal.client_name,
            Proposal.updated_at,
            ProposalMember.role,
            proposal_status,
        )
        .join(ProposalMember, membership)
        .subquery()
    )
    counts = dict.fromkeys(ProposalStatus, 0)
    for status, count in session.execute(
        select(visible.c.status, func.count()).group_by(visible.c.status)
    ):
        counts[ProposalStatus(status)] = count
    proposals = session.execute(
        select(visible).order_by(visible.c.updated_at.desc(), visible.c.id).limit(PROPOSAL_LIMIT)
    )

    links = (
        select(
            ShareLink.id,
            ShareLink.proposal_id,
            Proposal.title.label("proposal_title"),
            ShareLink.expires_at,
        )
        .join(Proposal, Proposal.id == ShareLink.proposal_id)
        .join(ProposalMember, membership)
        .where(is_owner, Proposal.archived_at.is_(None), is_active_link)
        .subquery()
    )
    active_count, expiring_count = session.execute(
        select(
            func.count(), func.count().filter(links.c.expires_at <= now + timedelta(days=7))
        ).select_from(links)
    ).one()
    active_links = session.execute(
        select(links).order_by(links.c.expires_at, links.c.id).limit(LINK_LIMIT)
    )

    generations = session.scalar(
        select(func.count())
        .select_from(ProposalVersion)
        .join(Proposal, Proposal.id == ProposalVersion.proposal_id)
        .join(ProposalMember, membership)
        .where(
            ProposalVersion.source == VersionSource.GENERATED,
            ProposalVersion.author_id == user_id,
            ProposalVersion.created_at >= now - timedelta(days=30),
            ProposalVersion.created_at <= now,
        )
    )
    version_events = (
        select(
            ProposalVersion.id.label("event_id"),
            Proposal.id.label("proposal_id"),
            Proposal.title.label("proposal_title"),
            cast(ProposalVersion.source, String).label("kind"),
            ProposalVersion.created_at.label("occurred_at"),
            ProposalVersion.number.label("version"),
        )
        .join(Proposal, Proposal.id == ProposalVersion.proposal_id)
        .join(ProposalMember, membership)
    )
    link_events = (
        select(
            ShareLink.id.label("event_id"),
            Proposal.id.label("proposal_id"),
            Proposal.title.label("proposal_title"),
            ShareLink.created_at,
            ShareLink.revoked_at,
        )
        .join(Proposal, Proposal.id == ShareLink.proposal_id)
        .join(ProposalMember, membership)
        .where(is_owner)
        .subquery()
    )
    link_identity = (
        link_events.c.event_id,
        link_events.c.proposal_id,
        link_events.c.proposal_title,
    )
    created_events = select(
        *link_identity,
        literal(ActivityKind.LINK_CREATED.value).label("kind"),
        link_events.c.created_at.label("occurred_at"),
        cast(literal(None), Integer).label("version"),
    )
    revoked_events = select(
        *link_identity,
        literal(ActivityKind.LINK_REVOKED.value).label("kind"),
        link_events.c.revoked_at.label("occurred_at"),
        cast(literal(None), Integer).label("version"),
    ).where(link_events.c.revoked_at.is_not(None))
    events = union_all(version_events, created_events, revoked_events).subquery()
    activity = session.execute(
        select(events)
        .order_by(events.c.occurred_at.desc(), events.c.event_id, events.c.kind)
        .limit(ACTIVITY_LIMIT)
    )

    return DashboardSummary(
        proposal_counts=counts,
        generations_last_30_days=generations or 0,
        active_link_count=active_count,
        expiring_link_count=expiring_count,
        recent_proposals=[RecentProposal.model_validate(row._mapping) for row in proposals],
        active_links=[ActiveLink.model_validate(row._mapping) for row in active_links],
        recent_activity=[Activity.model_validate(row._mapping) for row in activity],
    )
