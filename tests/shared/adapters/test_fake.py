import pytest

from app.shared.adapters.llm.base import GenerationRequest, TextDelta, Usage
from app.shared.adapters.llm.fake import FAKE_PROPOSAL, FakeProvider

REQUEST = GenerationRequest(system="s", prompt="p" * 40, max_tokens=100)


def test_streams_the_proposal_word_by_word() -> None:
    events = list(FakeProvider().stream(REQUEST))

    deltas = [event.text for event in events if isinstance(event, TextDelta)]
    assert "".join(deltas) == FAKE_PROPOSAL
    assert len(deltas) > 100
    assert isinstance(events[-1], Usage)


def test_pauses_before_each_word(monkeypatch: pytest.MonkeyPatch) -> None:
    pauses: list[float] = []
    monkeypatch.setattr("app.shared.adapters.llm.fake.time.sleep", pauses.append)

    events = list(FakeProvider(delay_ms=50).stream(REQUEST))

    assert pauses == [0.05] * (len(events) - 1)


def test_does_not_pause_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.shared.adapters.llm.fake.time.sleep", lambda _: pytest.fail("should not sleep")
    )

    list(FakeProvider().stream(REQUEST))
