import unicodedata
import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, SQLColumnExpression, false, func, or_, select, true
from sqlalchemy.orm import Session

from app.features.proposals.models import Proposal, ProposalMember, ProposalRole
from app.features.proposals.status import ProposalStatus, status_expression

# Portuguese accents folded in SQL, so search needs no database extension.
_ACCENTED = "áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ"
_PLAIN = "aaaaaeeeeiiiiooooouuuucnAAAAAEEEEIIIIOOOOOUUUUCN"


def add_proposal(
    session: Session, owner_id: uuid.UUID, title: str, client_name: str, briefing: str
) -> Proposal:
    proposal = Proposal(title=title, client_name=client_name, briefing=briefing, content="")
    session.add(proposal)
    session.flush()
    add_member(session, proposal.id, owner_id, ProposalRole.OWNER)
    return proposal


def add_member(
    session: Session, proposal_id: uuid.UUID, user_id: uuid.UUID, role: ProposalRole
) -> ProposalMember:
    member = ProposalMember(proposal_id=proposal_id, user_id=user_id, role=role)
    session.add(member)
    session.flush()
    return member


def get_with_role(
    session: Session, proposal_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Proposal, ProposalRole] | None:
    row = session.execute(
        select(Proposal, ProposalMember.role)
        .join(ProposalMember, ProposalMember.proposal_id == Proposal.id)
        .where(Proposal.id == proposal_id, ProposalMember.user_id == user_id)
    ).one_or_none()
    return (row[0], row[1]) if row else None


def _fold(column: SQLColumnExpression[str]) -> ColumnElement[str]:
    return func.lower(func.translate(column, _ACCENTED, _PLAIN))


def _search_pattern(query: str) -> str:
    plain = "".join(
        char for char in unicodedata.normalize("NFD", query) if not unicodedata.combining(char)
    ).lower()
    escaped = plain.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_for_user(
    session: Session,
    user_id: uuid.UUID,
    archived: bool,
    query: str | None,
    limit: int,
    offset: int,
    now: datetime,
) -> tuple[list[tuple[Proposal, ProposalRole, ProposalStatus]], int]:
    conditions = [
        ProposalMember.user_id == user_id,
        Proposal.archived_at.is_not(None) if archived else Proposal.archived_at.is_(None),
    ]
    if query:
        pattern = _search_pattern(query)
        conditions.append(
            or_(
                _fold(Proposal.title).like(pattern, escape="\\"),
                _fold(Proposal.client_name).like(pattern, escape="\\"),
            )
        )
    is_owner = ProposalMember.role == ProposalRole.OWNER
    base = (
        select(Proposal, ProposalMember.role, status_expression(is_owner, now))
        .join(ProposalMember, ProposalMember.proposal_id == Proposal.id)
        .where(*conditions)
    )
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.execute(
        base.order_by(Proposal.updated_at.desc(), Proposal.id).limit(limit).offset(offset)
    ).all()
    return [(row[0], row[1], ProposalStatus(row[2])) for row in rows], total


def status_of(
    session: Session, proposal_id: uuid.UUID, role: ProposalRole, now: datetime
) -> ProposalStatus:
    is_owner = true() if role == ProposalRole.OWNER else false()
    query = select(status_expression(is_owner, now)).where(Proposal.id == proposal_id)
    return ProposalStatus(session.execute(query).scalar_one())


def delete(session: Session, proposal: Proposal) -> None:
    session.delete(proposal)
