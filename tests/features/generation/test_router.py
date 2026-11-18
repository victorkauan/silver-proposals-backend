import json
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.conftest import AuthenticatedUser

from app.features.proposals import repository
from app.features.proposals.models import ProposalRole
from app.main import app
from app.shared.adapters.llm.base import (
    GenerationRequest,
    LLMUnavailableError,
    StreamEvent,
    TextDelta,
)
from app.shared.adapters.llm.factory import get_llm_provider
from app.shared.adapters.llm.fake import FAKE_PROPOSAL, FakeProvider
from app.shared.db import get_session_factory

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("database")]

MakeUser = Callable[[str], AuthenticatedUser]


class UnavailableProvider:
    model = "unavailable"

    def stream(self, request: GenerationRequest) -> Iterator[StreamEvent]:
        yield TextDelta("começo")
        raise LLMUnavailableError("throttlingexception")


class EmptyProvider:
    model = "empty"

    def stream(self, request: GenerationRequest) -> Iterator[StreamEvent]:
        yield TextDelta("   ")


def events(body: str) -> list[tuple[str, dict[str, Any]]]:
    parsed = []
    for block in body.strip().split("\n\n"):
        name_line, data_line = block.split("\n")
        parsed.append(
            (name_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: ")))
        )
    return parsed


def create(
    client: TestClient, owner: AuthenticatedUser, briefing: str = "Site com 5 páginas"
) -> str:
    response = client.post(
        "/proposals",
        json={"title": "Site", "client_name": "Padaria", "briefing": briefing},
        headers=owner.headers,
    )
    proposal_id: str = response.json()["id"]
    return proposal_id


def use(provider: object) -> None:
    app.dependency_overrides[get_llm_provider] = lambda: provider


def test_generation_streams_and_saves_the_content(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    proposal_id = create(client, owner)
    use(FakeProvider())

    response = client.post(f"/proposals/{proposal_id}/generate", headers=owner.headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    stream = events(response.text)
    assert stream[-1] == ("done", {"proposal_id": proposal_id})
    streamed = "".join(data["text"] for name, data in stream if name == "delta")
    assert streamed == FAKE_PROPOSAL
    saved = client.get(f"/proposals/{proposal_id}", headers=owner.headers).json()
    assert saved["content"] == FAKE_PROPOSAL.strip()


def test_editor_can_generate_and_viewer_cannot(client: TestClient, make_user: MakeUser) -> None:
    owner, editor, viewer = make_user("owner"), make_user("editor"), make_user("viewer")
    proposal_id = create(client, owner)
    with get_session_factory()() as session:
        repository.add_member(session, uuid.UUID(proposal_id), editor.id, ProposalRole.EDITOR)
        repository.add_member(session, uuid.UUID(proposal_id), viewer.id, ProposalRole.VIEWER)
        session.commit()
    use(FakeProvider())

    as_editor = client.post(f"/proposals/{proposal_id}/generate", headers=editor.headers)
    as_viewer = client.post(f"/proposals/{proposal_id}/generate", headers=viewer.headers)

    assert as_editor.status_code == 200
    assert as_viewer.status_code == 403


def test_non_member_and_anonymous_are_rejected(client: TestClient, make_user: MakeUser) -> None:
    owner, stranger = make_user("owner"), make_user("stranger")
    proposal_id = create(client, owner)

    assert (
        client.post(f"/proposals/{proposal_id}/generate", headers=stranger.headers).status_code
        == 404
    )
    assert client.post(f"/proposals/{proposal_id}/generate").status_code == 401


def test_generation_requires_a_briefing(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    proposal_id = create(client, owner, briefing="")

    response = client.post(f"/proposals/{proposal_id}/generate", headers=owner.headers)

    assert response.status_code == 422
    assert response.json()["code"] == "briefing_required"


def test_provider_failure_streams_an_error_and_keeps_the_content(
    client: TestClient, make_user: MakeUser
) -> None:
    owner = make_user("owner")
    proposal_id = create(client, owner)
    use(UnavailableProvider())

    response = client.post(f"/proposals/{proposal_id}/generate", headers=owner.headers)

    assert events(response.text)[-1] == (
        "error",
        {
            "code": "generation_unavailable",
            "message": "O serviço de IA está ocupado. Tente novamente em instantes.",
        },
    )
    assert client.get(f"/proposals/{proposal_id}", headers=owner.headers).json()["content"] == ""


def test_empty_output_is_a_failure(client: TestClient, make_user: MakeUser) -> None:
    owner = make_user("owner")
    proposal_id = create(client, owner)
    use(EmptyProvider())

    response = client.post(f"/proposals/{proposal_id}/generate", headers=owner.headers)

    assert events(response.text)[-1][1]["code"] == "generation_failed"
