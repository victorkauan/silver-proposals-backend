import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.conftest import AuthenticatedUser

from app.features.proposals import repository
from app.features.proposals.models import ProposalRole
from app.shared.db import get_session_factory

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("database")]

MakeUser = Callable[[str], AuthenticatedUser]
PROPOSAL = {
    "title": "Site institucional",
    "client_name": "Padaria Sol",
    "briefing": "Site com 5 páginas",
}


def create(client: TestClient, owner: AuthenticatedUser, **overrides: Any) -> dict[str, Any]:
    response = client.post("/proposals", json={**PROPOSAL, **overrides}, headers=owner.headers)
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body


def share(proposal_id: str, user: AuthenticatedUser, role: ProposalRole) -> None:
    with get_session_factory()() as session:
        repository.add_member(session, uuid.UUID(proposal_id), user.id, role)
        session.commit()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/proposals"),
        ("post", "/proposals"),
        ("get", f"/proposals/{uuid.uuid4()}"),
        ("patch", f"/proposals/{uuid.uuid4()}"),
        ("delete", f"/proposals/{uuid.uuid4()}"),
    ],
)
def test_anonymous_requests_are_rejected(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path, json={})

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_owner_creates_and_reads_a_proposal(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")

    created = create(client, owner)
    fetched = client.get(f"/proposals/{created['id']}", headers=owner.headers)

    assert created["role"] == "owner"
    assert created["content"] == ""
    assert fetched.status_code == 200
    assert fetched.json()["briefing"] == "Site com 5 páginas"


def test_create_rejects_blank_title(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")

    response = client.post("/proposals", json={**PROPOSAL, "title": "   "}, headers=owner.headers)

    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "title"


def test_list_shows_only_proposals_the_user_can_access(
    client: TestClient, make_user: MakeUser
) -> None:
    ana, bruno = make_user("ana"), make_user("bruno")
    own = create(client, ana, title="Da Ana")
    create(client, bruno, title="Do Bruno")
    shared = create(client, bruno, title="Compartilhada")
    share(shared["id"], ana, ProposalRole.VIEWER)

    body = client.get("/proposals", headers=ana.headers).json()

    assert body["total"] == 2
    assert {item["id"]: item["role"] for item in body["items"]} == {
        own["id"]: "owner",
        shared["id"]: "viewer",
    }


def test_list_paginates(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    for index in range(3):
        create(client, owner, title=f"Proposta {index}")

    page = client.get("/proposals?limit=2&offset=2", headers=owner.headers).json()

    assert page["total"] == 3
    assert len(page["items"]) == 1


def test_non_member_gets_not_found(client: TestClient, make_user: MakeUser) -> None:
    owner, stranger = make_user("owner"), make_user("stranger")
    proposal = create(client, owner)

    read = client.get(f"/proposals/{proposal['id']}", headers=stranger.headers)
    edit = client.patch(
        f"/proposals/{proposal['id']}", json={"title": "Hack"}, headers=stranger.headers
    )

    assert read.status_code == edit.status_code == 404
    assert read.json() == {"code": "proposal_not_found", "message": "Proposta não encontrada."}


def test_viewer_reads_but_cannot_change(client: TestClient, make_user: MakeUser) -> None:
    owner, viewer = make_user("owner"), make_user("viewer")
    proposal = create(client, owner)
    share(proposal["id"], viewer, ProposalRole.VIEWER)
    path = f"/proposals/{proposal['id']}"

    assert client.get(path, headers=viewer.headers).json()["role"] == "viewer"
    responses = [
        client.patch(path, json={"title": "Novo"}, headers=viewer.headers),
        client.post(f"{path}/archive", headers=viewer.headers),
        client.delete(path, headers=viewer.headers),
    ]
    assert [response.status_code for response in responses] == [403, 403, 403]
    assert responses[0].json()["code"] == "forbidden"


def test_editor_updates_but_cannot_archive_or_delete(
    client: TestClient, make_user: MakeUser
) -> None:
    owner, editor = make_user("owner"), make_user("editor")
    proposal = create(client, owner)
    share(proposal["id"], editor, ProposalRole.EDITOR)
    path = f"/proposals/{proposal['id']}"

    updated = client.patch(path, json={"client_name": "Padaria Lua"}, headers=editor.headers)

    assert updated.status_code == 200
    assert updated.json()["client_name"] == "Padaria Lua"
    assert updated.json()["title"] == "Site institucional"
    assert client.post(f"{path}/archive", headers=editor.headers).status_code == 403
    assert client.delete(path, headers=editor.headers).status_code == 403


def test_owner_archives_and_restores(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    proposal = create(client, owner)
    path = f"/proposals/{proposal['id']}"

    archived = client.post(f"{path}/archive", headers=owner.headers)
    active_list = client.get("/proposals", headers=owner.headers).json()
    archived_list = client.get("/proposals?archived=true", headers=owner.headers).json()
    restored = client.post(f"{path}/unarchive", headers=owner.headers)

    assert archived.json()["archived_at"] is not None
    assert active_list["total"] == 0
    assert archived_list["total"] == 1
    assert restored.json()["archived_at"] is None


def test_owner_deletes(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    proposal = create(client, owner)
    path = f"/proposals/{proposal['id']}"

    deleted = client.delete(path, headers=owner.headers)

    assert deleted.status_code == 204
    assert client.get(path, headers=owner.headers).status_code == 404


def test_invalid_proposal_id_is_a_validation_error(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")

    response = client.get("/proposals/not-a-uuid", headers=owner.headers)

    assert response.status_code == 422
