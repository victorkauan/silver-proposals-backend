import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from tests.conftest import AuthenticatedUser

from app.features.proposals import repository
from app.features.proposals.models import ProposalRole
from app.features.sharing.models import ShareLink
from app.shared.db import get_session_factory

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("database")]

MakeUser = Callable[[str], AuthenticatedUser]
NOT_FOUND = {"code": "share_link_not_found", "message": "Link inválido ou expirado."}


def create_proposal(client: TestClient, owner: AuthenticatedUser) -> str:
    proposal = client.post(
        "/proposals",
        json={"title": "Site", "client_name": "Padaria", "briefing": "briefing secreto"},
        headers=owner.headers,
    ).json()
    client.put(
        f"/proposals/{proposal['id']}/content",
        json={"content": "# Proposta\n\nTexto", "base_version": 0},
        headers=owner.headers,
    )
    proposal_id: str = proposal["id"]
    return proposal_id


def share(client: TestClient, owner: AuthenticatedUser, proposal_id: str, **body: Any) -> Any:
    return client.post(f"/proposals/{proposal_id}/share-links", json=body, headers=owner.headers)


def public(client: TestClient, token: str) -> Any:
    return client.post("/public/proposals/resolve", json={"token": token})


def test_valid_link_shows_only_public_fields(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    proposal_id = create_proposal(client, owner)

    created = share(client, owner, proposal_id, expires_in_days=3)
    response = public(client, created.json()["token"])

    assert created.status_code == 201
    assert created.json()["active"] is True
    assert len(created.json()["token"]) >= 43
    assert response.status_code == 200
    assert set(response.json()) == {"title", "client_name", "content", "updated_at"}
    assert response.json()["content"] == "# Proposta\n\nTexto"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-robots-tag"] == "noindex"
    assert client.get(f"/public/proposals/{created.json()['token']}").json() == response.json()


def test_expired_link_is_not_found(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    proposal_id = create_proposal(client, owner)
    token = share(client, owner, proposal_id).json()["token"]
    with get_session_factory()() as session:
        session.execute(
            update(ShareLink).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        session.commit()

    response = public(client, token)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_revoked_link_is_not_found(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    proposal_id = create_proposal(client, owner)
    created = share(client, owner, proposal_id).json()

    revoked = client.delete(
        f"/proposals/{proposal_id}/share-links/{created['id']}", headers=owner.headers
    )
    listed = client.get(f"/proposals/{proposal_id}/share-links", headers=owner.headers).json()

    assert revoked.status_code == 204
    assert public(client, created["token"]).json() == NOT_FOUND
    assert listed[0]["active"] is False
    assert listed[0]["revoked_at"] is not None


def test_missing_link_is_not_found(client: TestClient) -> None:
    response = public(client, "token-que-nao-existe")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_archived_proposal_is_not_shared(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    proposal_id = create_proposal(client, owner)
    token = share(client, owner, proposal_id).json()["token"]

    client.post(f"/proposals/{proposal_id}/archive", headers=owner.headers)

    assert public(client, token).json() == NOT_FOUND


def test_only_the_owner_manages_links(client: TestClient, make_user: MakeUser) -> None:
    owner, editor, stranger = make_user("owner"), make_user("editor"), make_user("stranger")
    proposal_id = create_proposal(client, owner)
    with get_session_factory()() as session:
        repository.add_member(session, uuid.UUID(proposal_id), editor.id, ProposalRole.EDITOR)
        session.commit()

    assert share(client, editor, proposal_id).status_code == 403
    assert share(client, stranger, proposal_id).status_code == 404
    assert client.post(f"/proposals/{proposal_id}/share-links", json={}).status_code == 401
    assert (
        client.get(f"/proposals/{proposal_id}/share-links", headers=editor.headers).status_code
        == 403
    )


def test_revoking_an_unknown_link_is_not_found(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    proposal_id = create_proposal(client, owner)

    response = client.delete(
        f"/proposals/{proposal_id}/share-links/{uuid.uuid4()}", headers=owner.headers
    )

    assert response.status_code == 404


@pytest.mark.parametrize("days", [0, 91])
def test_expiry_must_be_between_1_and_90_days(
    client: TestClient, make_user: MakeUser, days: int
) -> None:
    owner = make_user("owner")
    proposal_id = create_proposal(client, owner)

    assert share(client, owner, proposal_id, expires_in_days=days).status_code == 422


def test_token_is_stored_only_as_a_hash(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    proposal_id = create_proposal(client, owner)
    token = share(client, owner, proposal_id).json()["token"]

    with get_session_factory()() as session:
        stored = session.query(ShareLink).one()

    assert stored.token_hash != token
    assert len(stored.token_hash) == 64


def test_public_limit_applies_across_tokens_and_resolver_routes(client: TestClient) -> None:
    for index in range(60):
        assert public(client, f"unknown-{index}").status_code == 404

    assert client.get("/public/proposals/another-unknown").status_code == 429
