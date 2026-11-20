import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.conftest import AuthenticatedUser

from app.features.proposals import repository
from app.features.proposals.models import (
    Proposal,
    ProposalMember,
    ProposalRole,
    ProposalVersion,
    VersionSource,
)
from app.shared.db import get_session_factory

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("database")]

MakeUser = Callable[[str], AuthenticatedUser]


def create(client: TestClient, owner: AuthenticatedUser, **fields: Any) -> dict[str, Any]:
    body = {"title": "Site institucional", "client_name": "Padaria Sol", **fields}
    response = client.post("/proposals", json=body, headers=owner.headers)
    assert response.status_code == 201
    created: dict[str, Any] = response.json()
    return created


def statuses(client: TestClient, user: AuthenticatedUser, **params: Any) -> dict[str, str]:
    page = client.get("/proposals", params=params, headers=user.headers).json()
    return {item["title"]: item["status"] for item in page["items"]}


def add_generated_version(proposal_id: str, author: AuthenticatedUser) -> None:
    with get_session_factory()() as session:
        proposal = session.get(Proposal, uuid.UUID(proposal_id))
        assert proposal is not None
        proposal.version = 1
        proposal.content = "Generated draft"
        session.add(
            ProposalVersion(
                proposal_id=proposal.id,
                number=1,
                content="Generated draft",
                source=VersionSource.GENERATED,
                author_id=author.id,
            )
        )
        session.commit()


def test_status_follows_the_proposal_lifecycle(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    draft = create(client, owner, title="Rascunho")
    generated = create(client, owner, title="Gerada")
    edited = create(client, owner, title="Editada")
    shared = create(client, owner, title="Compartilhada")
    archived = create(client, owner, title="Arquivada")

    add_generated_version(generated["id"], owner)
    saved = client.put(
        f"/proposals/{edited['id']}/content",
        json={"content": "Texto", "base_version": 0},
        headers=owner.headers,
    )
    client.post(
        f"/proposals/{shared['id']}/share-links", json={"expires_in_days": 7}, headers=owner.headers
    )
    client.post(f"/proposals/{archived['id']}/archive", headers=owner.headers)

    assert draft["status"] == "draft"
    assert saved.json()["status"] == "edited"
    assert statuses(client, owner) == {
        "Rascunho": "draft",
        "Gerada": "generated",
        "Editada": "edited",
        "Compartilhada": "shared",
    }
    assert statuses(client, owner, archived=True) == {"Arquivada": "archived"}
    detail = client.get(f"/proposals/{shared['id']}", headers=owner.headers).json()
    assert detail["status"] == "shared"


def test_shared_status_is_only_shown_to_owners(client: TestClient, make_user: MakeUser) -> None:
    owner, editor = make_user("owner"), make_user("editor")
    proposal = create(client, owner, title="Compartilhada")
    with get_session_factory()() as session:
        repository.add_member(session, uuid.UUID(proposal["id"]), editor.id, ProposalRole.EDITOR)
        session.commit()
    client.post(
        f"/proposals/{proposal['id']}/share-links",
        json={"expires_in_days": 7},
        headers=owner.headers,
    )

    detail = client.get(f"/proposals/{proposal['id']}", headers=editor.headers).json()

    assert statuses(client, owner) == {"Compartilhada": "shared"}
    assert statuses(client, editor) == {"Compartilhada": "draft"}
    assert detail["status"] == "draft"


def test_revoked_or_expired_links_do_not_count_as_shared(
    client: TestClient, make_user: MakeUser
) -> None:
    owner = make_user("owner")
    revoked = create(client, owner, title="Revogada")
    link = client.post(
        f"/proposals/{revoked['id']}/share-links",
        json={"expires_in_days": 7},
        headers=owner.headers,
    ).json()
    client.delete(f"/proposals/{revoked['id']}/share-links/{link['id']}", headers=owner.headers)

    assert statuses(client, owner) == {"Revogada": "draft"}


def test_search_ignores_case_and_accents_in_title_and_client(
    client: TestClient, make_user: MakeUser
) -> None:
    owner = make_user("owner")
    create(client, owner, title="Plano de Comunicação", client_name="Clínica Saúde")
    create(client, owner, title="Site institucional", client_name="Padaria São João")
    create(client, owner, title="Consultoria fiscal", client_name="Escritório Lima")

    assert set(statuses(client, owner, q="COMUNICACAO")) == {"Plano de Comunicação"}
    assert set(statuses(client, owner, q="sao joão")) == {"Site institucional"}
    assert set(statuses(client, owner, q="  ")) == {
        "Plano de Comunicação",
        "Site institucional",
        "Consultoria fiscal",
    }


def test_search_treats_wildcards_as_text(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    create(client, owner, title="Desconto de 50% à vista")
    create(client, owner, title="Desconto de 500 reais")

    assert set(statuses(client, owner, q="50%")) == {"Desconto de 50% à vista"}
    assert statuses(client, owner, q="_") == {}


def test_search_and_pagination_reach_beyond_the_first_hundred(
    client: TestClient, make_user: MakeUser
) -> None:
    owner = make_user("owner")
    start = datetime.now(UTC)
    with get_session_factory()() as session:
        for index in range(105):
            proposal = Proposal(
                title=f"Proposta {index:03d}",
                client_name="Cliente",
                updated_at=start - timedelta(minutes=index),
            )
            session.add(proposal)
            session.flush()
            session.add(
                ProposalMember(proposal_id=proposal.id, user_id=owner.id, role=ProposalRole.OWNER)
            )
        session.commit()

    last_page = client.get("/proposals?limit=20&offset=100", headers=owner.headers).json()
    found = client.get("/proposals?q=proposta 104", headers=owner.headers).json()

    assert last_page["total"] == 105
    assert [item["title"] for item in last_page["items"]] == [
        f"Proposta {index:03d}" for index in range(100, 105)
    ]
    assert found["total"] == 1
    assert found["items"][0]["title"] == "Proposta 104"


def test_search_is_limited_in_length(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")

    response = client.get("/proposals", params={"q": "x" * 201}, headers=owner.headers)

    assert response.status_code == 422
