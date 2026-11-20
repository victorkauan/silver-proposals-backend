import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.conftest import AuthenticatedUser

from app.features.proposals.models import (
    Proposal,
    ProposalMember,
    ProposalRole,
    ProposalVersion,
    VersionSource,
)
from app.features.sharing.models import ShareLink
from app.shared.db import get_session_factory

MakeUser = Callable[[str], AuthenticatedUser]
pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("database")]


def add_proposal(
    session: Session,
    user: AuthenticatedUser,
    title: str,
    now: datetime,
    *,
    source: VersionSource | None = None,
    archived: bool = False,
    version_at: datetime | None = None,
) -> Proposal:
    proposal = Proposal(
        title=title,
        client_name="Client",
        updated_at=now,
        archived_at=now if archived else None,
        version=int(source is not None),
    )
    session.add(proposal)
    session.flush()
    session.add(ProposalMember(proposal_id=proposal.id, user_id=user.id, role=ProposalRole.OWNER))
    if source is not None:
        session.add(
            ProposalVersion(
                proposal_id=proposal.id,
                number=1,
                content="Version content",
                source=source,
                author_id=user.id,
                created_at=version_at or now,
            )
        )
    return proposal


def add_link(
    session: Session,
    proposal: Proposal,
    now: datetime,
    days: int,
    *,
    revoked: bool = False,
) -> ShareLink:
    link = ShareLink(
        proposal_id=proposal.id,
        token_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        created_at=now - timedelta(minutes=2),
        expires_at=now + timedelta(days=days),
        revoked_at=now - timedelta(minutes=1) if revoked else None,
    )
    session.add(link)
    return link


def test_empty_summary_requires_authentication(client: TestClient, make_user: MakeUser) -> None:
    assert client.get("/dashboard/summary").status_code == 401
    user = make_user("new")
    response = client.get("/dashboard/summary", headers=user.headers)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "proposal_counts": dict.fromkeys(("draft", "generated", "edited", "shared", "archived"), 0),
        "generations_last_30_days": 0,
        "active_link_count": 0,
        "expiring_link_count": 0,
        "recent_proposals": [],
        "active_links": [],
        "recent_activity": [],
    }


def test_summary_respects_membership_roles_archives_revocations_and_time_windows(
    client: TestClient, make_user: MakeUser
) -> None:
    owner, other = make_user("owner"), make_user("other")
    now = datetime.now(UTC)
    with get_session_factory()() as session:
        add_proposal(session, owner, "Draft", now)
        add_proposal(session, owner, "Generated", now, source=VersionSource.GENERATED)
        edited = add_proposal(session, owner, "Edited", now, source=VersionSource.RESTORED)
        archived = add_proposal(
            session,
            owner,
            "Archived",
            now,
            source=VersionSource.GENERATED,
            archived=True,
            version_at=now - timedelta(days=31),
        )
        shared = add_proposal(session, owner, "Shared", now, source=VersionSource.EDITED)
        unrelated = add_proposal(session, other, "Unrelated", now, source=VersionSource.GENERATED)
        session.add(
            ProposalMember(proposal_id=shared.id, user_id=other.id, role=ProposalRole.VIEWER)
        )
        session.add(
            ProposalMember(proposal_id=edited.id, user_id=other.id, role=ProposalRole.EDITOR)
        )
        expiring = add_link(session, shared, now, 6)
        later = add_link(session, shared, now, 8)
        add_link(session, shared, now, 3, revoked=True)
        add_link(session, edited, now, -1)
        add_link(session, archived, now, 1)
        add_link(session, unrelated, now, 1)
        session.commit()
        expiring_id, later_id = str(expiring.id), str(later.id)

    response = client.get("/dashboard/summary", headers=owner.headers)
    assert response.status_code == 200
    data = response.json()
    assert data["proposal_counts"] == {
        "draft": 1,
        "generated": 1,
        "edited": 1,
        "shared": 1,
        "archived": 1,
    }
    assert data["generations_last_30_days"] == 1
    assert data["active_link_count"] == 2 and data["expiring_link_count"] == 1
    assert [item["id"] for item in data["active_links"]] == [expiring_id, later_id]
    assert {item["title"] for item in data["recent_proposals"]} == {
        "Draft",
        "Generated",
        "Edited",
        "Archived",
        "Shared",
    }
    assert {item["kind"] for item in data["recent_activity"]} >= {
        "generated",
        "edited",
        "restored",
        "link_created",
        "link_revoked",
    }
    assert "Unrelated" not in response.text
    assert "token_hash" not in response.text

    response = client.get("/dashboard/summary", headers=other.headers)
    assert response.status_code == 200
    data = response.json()
    assert {item["title"]: (item["role"], item["status"]) for item in data["recent_proposals"]} == {
        "Unrelated": ("owner", "shared"),
        "Shared": ("viewer", "edited"),
        "Edited": ("editor", "edited"),
    }
    assert data["generations_last_30_days"] == 1
    assert [item["proposal_title"] for item in data["active_links"]] == ["Unrelated"]
    assert {
        item["proposal_title"]
        for item in data["recent_activity"]
        if item["kind"].startswith("link_")
    } == {"Unrelated"}
    assert any(
        item["proposal_title"] == "Shared" and item["kind"] == "edited"
        for item in data["recent_activity"]
    )


def test_summary_bounds_each_recent_list_without_truncating_counters(
    client: TestClient, make_user: MakeUser
) -> None:
    user = make_user("many")
    now = datetime.now(UTC)
    with get_session_factory()() as session:
        for index in range(10):
            timestamp = now - timedelta(minutes=index)
            item = add_proposal(
                session, user, f"Proposal {index}", timestamp, source=VersionSource.GENERATED
            )
            add_link(session, item, timestamp, index + 1)
        session.commit()

    data = client.get("/dashboard/summary", headers=user.headers).json()

    assert data["proposal_counts"]["shared"] == 10
    assert data["generations_last_30_days"] == 10
    assert data["active_link_count"] == 10 and data["expiring_link_count"] == 7
    assert [item["title"] for item in data["recent_proposals"]] == [
        f"Proposal {i}" for i in range(5)
    ]
    assert [item["proposal_title"] for item in data["active_links"]] == [
        f"Proposal {i}" for i in range(5)
    ]
    assert len(data["recent_activity"]) == 8
    dates = [item["occurred_at"] for item in data["recent_activity"]]
    assert dates == sorted(dates, reverse=True)
