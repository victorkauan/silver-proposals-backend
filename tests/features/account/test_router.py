import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.features.auth.models import PRIVACY_NOTICE_VERSION, RefreshToken, User
from app.features.proposals.models import Proposal, ProposalRole, ProposalVersion
from app.features.proposals.repository import add_member
from app.features.sharing.models import ShareLink
from app.main import purge_once
from app.shared.db import get_session_factory

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("database")]

PASSWORD = "uma senha longa"


def signup(client: TestClient, email: str = "ana@example.com", name: str = "Ana Lima") -> Any:
    response = client.post(
        "/auth/register",
        json={"email": email, "name": name, "password": PASSWORD, "accept_privacy": True},
    )
    assert response.status_code == 201
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]


def create_proposal(client: TestClient, headers: dict[str, str], title: str = "Site") -> str:
    response = client.post(
        "/proposals",
        headers=headers,
        json={"title": title, "client_name": "Padaria", "briefing": "Quero um site."},
    )
    assert response.status_code == 201
    proposal_id: str = response.json()["id"]
    return proposal_id


def save_content(client: TestClient, headers: dict[str, str], proposal_id: str) -> None:
    response = client.put(
        f"/proposals/{proposal_id}/content",
        headers=headers,
        json={"content": "# Proposta", "base_version": 0},
    )
    assert response.status_code == 200


def test_update_profile_changes_the_name(client: TestClient) -> None:
    headers, _ = signup(client)

    response = client.patch("/account", headers=headers, json={"name": "  Ana Souza  "})

    assert response.status_code == 200
    assert response.json()["name"] == "Ana Souza"


def test_update_profile_rejects_an_empty_name(client: TestClient) -> None:
    headers, _ = signup(client)

    assert client.patch("/account", headers=headers, json={"name": "  "}).status_code == 422


def test_account_routes_require_authentication(client: TestClient) -> None:
    assert client.patch("/account", json={"name": "Ana"}).status_code == 401
    assert client.get("/account/export").status_code == 401
    assert client.post("/account/delete", json={"password": PASSWORD}).status_code == 401


def test_change_email_with_the_right_password(client: TestClient) -> None:
    headers, _ = signup(client)

    response = client.put(
        "/account/email", headers=headers, json={"email": "Nova@Example.com", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "nova@example.com"
    login = client.post("/auth/login", json={"email": "nova@example.com", "password": PASSWORD})
    assert login.status_code == 200


def test_change_email_rejects_a_wrong_password(client: TestClient) -> None:
    headers, _ = signup(client)

    response = client.put(
        "/account/email", headers=headers, json={"email": "nova@example.com", "password": "errada"}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "invalid_password"


def test_change_email_rejects_an_address_in_use(client: TestClient) -> None:
    signup(client, email="bia@example.com", name="Bia")
    headers, _ = signup(client)

    response = client.put(
        "/account/email", headers=headers, json={"email": "BIA@example.com", "password": PASSWORD}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "email_taken"


def test_change_email_to_the_same_address_is_allowed(client: TestClient) -> None:
    headers, _ = signup(client)

    response = client.put(
        "/account/email", headers=headers, json={"email": "ana@example.com", "password": PASSWORD}
    )

    assert response.status_code == 200


def test_accepting_the_current_privacy_notice(client: TestClient) -> None:
    headers, user = signup(client)
    with get_session_factory()() as session:
        stored = session.get(User, uuid.UUID(user["id"]))
        assert stored is not None
        stored.privacy_version = "2000-01-01"
        session.commit()
    assert client.get("/auth/me", headers=headers).json()["privacy_up_to_date"] is False

    response = client.post("/account/privacy-acceptance", headers=headers)

    assert response.status_code == 200
    assert response.json()["privacy_up_to_date"] is True
    with get_session_factory()() as session:
        stored = session.get(User, uuid.UUID(user["id"]))
        assert stored is not None
        assert stored.privacy_version == PRIVACY_NOTICE_VERSION


def test_export_returns_the_users_data_as_an_attachment(client: TestClient) -> None:
    headers, user = signup(client)
    proposal_id = create_proposal(client, headers)
    save_content(client, headers, proposal_id)
    client.post(
        f"/proposals/{proposal_id}/share-links", headers=headers, json={"expires_in_days": 7}
    )

    response = client.get("/account/export", headers=headers)

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["account"]["email"] == "ana@example.com"
    assert data["account"]["privacy_version"] == PRIVACY_NOTICE_VERSION
    assert data["proposals"][0]["id"] == proposal_id
    assert data["proposals"][0]["role"] == "owner"
    assert data["authored_versions"][0]["content"] == "# Proposta"
    assert len(data["share_links_created"]) == 1
    assert len(data["sessions"]) == 1
    text = response.text
    assert "password_hash" not in text
    assert "token_hash" not in text
    assert user["id"] == data["account"]["id"]


def test_delete_account_requires_the_password(client: TestClient) -> None:
    headers, _ = signup(client)

    response = client.post("/account/delete", headers=headers, json={"password": "errada"})

    assert response.status_code == 403
    assert client.get("/auth/me", headers=headers).status_code == 200


def test_delete_account_removes_the_user_and_sole_owned_proposals(client: TestClient) -> None:
    bia_headers, bia = signup(client, email="bia@example.com", name="Bia")
    headers, user = signup(client)
    own = create_proposal(client, headers, "Só da Ana")
    shared = create_proposal(client, headers, "Compartilhada")
    save_content(client, headers, shared)
    client.post(f"/proposals/{shared}/share-links", headers=headers, json={"expires_in_days": 7})
    bia_owned = create_proposal(client, bia_headers, "Da Bia")
    with get_session_factory()() as session:
        add_member(session, uuid.UUID(shared), uuid.UUID(bia["id"]), ProposalRole.OWNER)
        add_member(session, uuid.UUID(bia_owned), uuid.UUID(user["id"]), ProposalRole.EDITOR)
        session.commit()

    response = client.post("/account/delete", headers=headers, json={"password": PASSWORD})

    assert response.status_code == 204
    assert "refresh_token=" in response.headers["set-cookie"]
    with get_session_factory()() as session:
        assert session.get(User, uuid.UUID(user["id"])) is None
        assert session.get(Proposal, uuid.UUID(own)) is None
        assert session.get(Proposal, uuid.UUID(shared)) is not None
        assert session.get(Proposal, uuid.UUID(bia_owned)) is not None
        version = session.scalar(
            select(ProposalVersion).where(ProposalVersion.proposal_id == uuid.UUID(shared))
        )
        assert version is not None
        assert version.author_id is None
        link = session.scalar(select(ShareLink).where(ShareLink.proposal_id == uuid.UUID(shared)))
        assert link is not None
        assert link.created_by is None
        tokens = session.scalar(
            select(func.count())
            .select_from(RefreshToken)
            .where(RefreshToken.user_id == uuid.UUID(user["id"]))
        )
        assert tokens == 0
    login = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
    assert login.status_code == 401
    assert client.get(f"/proposals/{shared}", headers=bia_headers).status_code == 200


def test_purge_removes_only_expired_refresh_tokens(client: TestClient) -> None:
    signup(client)
    signup(client, email="bia@example.com", name="Bia")
    with get_session_factory()() as session:
        expired = session.scalars(select(RefreshToken)).first()
        assert expired is not None
        expired.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()

    assert purge_once() == 1

    with get_session_factory()() as session:
        assert session.scalar(select(func.count()).select_from(RefreshToken)) == 1
