import io
import json
from collections.abc import Iterator
from email.message import Message
from typing import IO, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from app.shared.adapters.llm.base import (
    GenerationRequest,
    LLMFailureError,
    LLMTimeoutError,
    LLMUnavailableError,
    TextDelta,
    Usage,
)
from app.shared.adapters.llm.deepinfra import DeepInfraProvider

REQUEST = GenerationRequest(system="system", prompt="prompt", max_tokens=512)


def sse(*chunks: dict[str, Any] | str) -> bytes:
    lines = [f"data: {c if isinstance(c, str) else json.dumps(c)}\n\n" for c in chunks]
    return ("".join(lines)).encode()


class Opener:
    def __init__(self, body: bytes = b"", error: Exception | None = None) -> None:
        self.body = body
        self.error = error
        self.requests: list[tuple[Request, float]] = []

    def __call__(self, request: Request, timeout: float) -> IO[bytes]:
        self.requests.append((request, timeout))
        if self.error:
            raise self.error
        return io.BytesIO(self.body)


def provider(opener: Opener) -> DeepInfraProvider:
    return DeepInfraProvider(
        "org/model", "secret-key", "https://example.test/v1/openai/", 30, opener
    )


def delta(text: str) -> dict[str, Any]:
    return {"choices": [{"delta": {"content": text}}]}


def http_error(status: int) -> HTTPError:
    return HTTPError("https://example.test", status, "boom", Message(), io.BytesIO(b"{}"))


def test_streams_text_and_usage_and_sends_an_openai_request() -> None:
    opener = Opener(
        sse(
            {"choices": [{"delta": {"role": "assistant"}}]},
            delta("# Pro"),
            delta("posta"),
            {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 3}},
            "[DONE]",
        )
    )

    events = list(provider(opener).stream(REQUEST))

    assert events == [TextDelta("# Pro"), TextDelta("posta"), Usage(10, 3)]
    request, timeout = opener.requests[0]
    assert request.full_url == "https://example.test/v1/openai/chat/completions"
    assert request.get_header("Authorization") == "Bearer secret-key"
    assert timeout == 30
    assert isinstance(request.data, bytes)
    body = json.loads(request.data)
    assert body["model"] == "org/model"
    assert body["max_tokens"] == 512
    assert body["stream"] is True
    assert body["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "prompt"},
    ]


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (429, LLMUnavailableError),
        (503, LLMUnavailableError),
        (504, LLMTimeoutError),
        (401, LLMFailureError),
        (400, LLMFailureError),
    ],
)
def test_maps_http_errors(status: int, expected: type[Exception]) -> None:
    with pytest.raises(expected, match=f"http_{status}"):
        list(provider(Opener(error=http_error(status))).stream(REQUEST))


def test_maps_timeouts_and_connection_errors() -> None:
    with pytest.raises(LLMTimeoutError):
        list(provider(Opener(error=TimeoutError())).stream(REQUEST))
    with pytest.raises(LLMTimeoutError):
        list(provider(Opener(error=URLError(TimeoutError()))).stream(REQUEST))
    with pytest.raises(LLMUnavailableError):
        list(provider(Opener(error=URLError("unreachable"))).stream(REQUEST))


def test_maps_a_timeout_in_the_middle_of_the_stream() -> None:
    class Broken(io.BytesIO):
        def __iter__(self) -> Iterator[bytes]:
            yield sse(delta("parcial"))
            raise TimeoutError

    class BrokenOpener(Opener):
        def __call__(self, request: Request, timeout: float) -> IO[bytes]:
            return Broken()

    stream = provider(BrokenOpener()).stream(REQUEST)

    assert next(stream) == TextDelta("parcial")
    with pytest.raises(LLMTimeoutError):
        next(stream)


def test_rejects_malformed_chunks() -> None:
    with pytest.raises(LLMFailureError, match="invalid_response"):
        list(provider(Opener(sse("{not json"))).stream(REQUEST))


def test_refuses_a_base_url_without_https() -> None:
    with pytest.raises(ValueError, match="https"):
        DeepInfraProvider("org/model", "secret-key", "http://example.test", 30, Opener())
