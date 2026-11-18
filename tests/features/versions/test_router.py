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


def create(client: TestClient, owner: AuthenticatedUser) -> str:
    response = client.post(
        "/proposals",
        json={"title": "Site", "client_name": "Padaria", "briefing": "Site"},
        headers=owner.headers,
    )
    proposal_id: str = response.json()["id"]
    return proposal_id


def share(proposal_id: str, user: AuthenticatedUser, role: ProposalRole) -> None:
    with get_session_factory()() as session:
        repository.add_member(session, uuid.UUID(proposal_id), user.id, role)
        session.commit()


def save(
    client: TestClient, user: AuthenticatedUser, proposal_id: str, content: str, base: int
) -> Any:
    return client.put(
        f"/proposals/{proposal_id}/content",
        json={"content": content, "base_version": base},
        headers=user.headers,
    )


def test_editor_saves_content_as_a_new_version(client: TestClient, make_user: MakeUser) -> None:
    owner, editor = make_user("owner"), make_user("editor")
    proposal_id = create(client, owner)
    share(proposal_id, editor, ProposalRole.EDITOR)

    response = save(client, editor, proposal_id, "# Proposta\n\nTexto", base=0)

    assert response.status_code == 200
    assert response.json()["content"] == "# Proposta\n\nTexto"
    assert response.json()["version"] == 1
    history = client.get(f"/proposals/{proposal_id}/versions", headers=owner.headers).json()
    assert history["total"] == 1
    assert history["items"][0]["source"] == "edited"
    assert history["items"][0]["author_name"] == "editor"
    assert history["items"][0]["content_chars"] == len("# Proposta\n\nTexto")


def test_stale_base_version_is_a_conflict(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    proposal_id = create(client, owner)
    save(client, owner, proposal_id, "primeira", base=0)

    stale = save(client, owner, proposal_id, "edição desatualizada", base=0)

    assert stale.status_code == 409
    assert stale.json()["code"] == "version_conflict"
    current = client.get(f"/proposals/{proposal_id}", headers=owner.headers).json()
    assert current["content"] == "primeira"
    assert current["version"] == 1


def test_saving_identical_content_does_not_create_a_version(
    client: TestClient, make_user: MakeUser
) -> None:
    owner = make_user("owner")
    proposal_id = create(client, owner)
    save(client, owner, proposal_id, "igual", base=0)

    response = save(client, owner, proposal_id, "igual", base=1)

    assert response.json()["version"] == 1
    assert (
        client.get(f"/proposals/{proposal_id}/versions", headers=owner.headers).json()["total"] == 1
    )


def test_history_is_newest_first_and_versions_are_readable(
    client: TestClient, make_user: MakeUser
) -> None:
    owner = make_user("owner")
    proposal_id = create(client, owner)
    save(client, owner, proposal_id, "v1", base=0)
    save(client, owner, proposal_id, "v2", base=1)

    history = client.get(f"/proposals/{proposal_id}/versions", headers=owner.headers).json()
    first = client.get(f"/proposals/{proposal_id}/versions/1", headers=owner.headers)
    missing = client.get(f"/proposals/{proposal_id}/versions/99", headers=owner.headers)

    assert [item["number"] for item in history["items"]] == [2, 1]
    assert first.json()["content"] == "v1"
    assert missing.status_code == 404
    assert missing.json()["code"] == "version_not_found"


def test_restore_creates_a_new_version_with_old_content(
    client: TestClient, make_user: MakeUser
) -> None:
    owner = make_user("owner")
    proposal_id = create(client, owner)
    save(client, owner, proposal_id, "v1", base=0)
    save(client, owner, proposal_id, "v2", base=1)

    restored = client.post(f"/proposals/{proposal_id}/versions/1/restore", headers=owner.headers)

    assert restored.status_code == 200
    assert restored.json()["content"] == "v1"
    assert restored.json()["version"] == 3
    history = client.get(f"/proposals/{proposal_id}/versions", headers=owner.headers).json()
    assert [(item["number"], item["source"]) for item in history["items"]] == [
        (3, "restored"),
        (2, "edited"),
        (1, "edited"),
    ]


def test_viewer_reads_history_but_cannot_edit_or_restore(
    client: TestClient, make_user: MakeUser
) -> None:
    owner, viewer = make_user("owner"), make_user("viewer")
    proposal_id = create(client, owner)
    save(client, owner, proposal_id, "v1", base=0)
    share(proposal_id, viewer, ProposalRole.VIEWER)

    history = client.get(f"/proposals/{proposal_id}/versions", headers=viewer.headers)
    edit = save(client, viewer, proposal_id, "tentativa", base=1)
    restore = client.post(f"/proposals/{proposal_id}/versions/1/restore", headers=viewer.headers)

    assert history.status_code == 200
    assert edit.status_code == restore.status_code == 403
    assert edit.json()["code"] == "forbidden"


def test_non_member_and_anonymous_are_rejected(client: TestClient, make_user: MakeUser) -> None:
    owner, stranger = make_user("owner"), make_user("stranger")
    proposal_id = create(client, owner)

    assert save(client, stranger, proposal_id, "x", base=0).status_code == 404
    assert (
        client.get(f"/proposals/{proposal_id}/versions", headers=stranger.headers).status_code
        == 404
    )
    assert client.get(f"/proposals/{proposal_id}/versions").status_code == 401
