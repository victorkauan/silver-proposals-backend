from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, cast

import pytest
from botocore.exceptions import ClientError, NoCredentialsError, ReadTimeoutError

from app.shared.adapters.llm.base import (
    GenerationRequest,
    LLMFailureError,
    LLMTimeoutError,
    LLMUnavailableError,
    TextDelta,
    Usage,
)
from app.shared.adapters.llm.bedrock import BedrockProvider

if TYPE_CHECKING:
    from types_boto3_bedrock_runtime import BedrockRuntimeClient

REQUEST = GenerationRequest(system="system", prompt="prompt", max_tokens=512)


class FakeClient:
    def __init__(
        self, events: Iterator[dict[str, Any]] | None = None, error: Exception | None = None
    ):
        self.events = events or iter([])
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def converse_stream(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"stream": self.events}


def provider(client: FakeClient) -> BedrockProvider:
    return BedrockProvider("us.test-model", "us-east-1", 30, cast("BedrockRuntimeClient", client))


def client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "boom"}}, "ConverseStream")


def test_streams_text_and_usage_and_sets_max_tokens() -> None:
    stream: list[dict[str, Any]] = [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockDelta": {"delta": {"text": "# Pro"}}},
        {"contentBlockDelta": {"delta": {"text": "posta"}}},
        {"messageStop": {"stopReason": "end_turn"}},
        {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 3}}},
    ]
    client = FakeClient(iter(stream))

    events = list(provider(client).stream(REQUEST))

    assert events == [TextDelta("# Pro"), TextDelta("posta"), Usage(10, 3)]
    call = client.calls[0]
    assert call["modelId"] == "us.test-model"
    assert call["inferenceConfig"]["maxTokens"] == 512
    assert call["system"] == [{"text": "system"}]


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("ThrottlingException", LLMUnavailableError),
        ("ServiceUnavailableException", LLMUnavailableError),
        ("ModelTimeoutException", LLMTimeoutError),
        ("AccessDeniedException", LLMFailureError),
        ("ValidationException", LLMFailureError),
    ],
)
def test_maps_client_errors(code: str, expected: type[Exception]) -> None:
    with pytest.raises(expected):
        list(provider(FakeClient(error=client_error(code))).stream(REQUEST))


def test_maps_errors_raised_in_the_middle_of_the_stream() -> None:
    def broken() -> Iterator[dict[str, Any]]:
        yield {"contentBlockDelta": {"delta": {"text": "parcial"}}}
        raise client_error("throttlingException")

    stream = provider(FakeClient(broken())).stream(REQUEST)

    assert next(stream) == TextDelta("parcial")
    with pytest.raises(LLMUnavailableError):
        next(stream)


def test_maps_read_timeouts() -> None:
    with pytest.raises(LLMTimeoutError):
        list(provider(FakeClient(error=ReadTimeoutError(endpoint_url="x"))).stream(REQUEST))


def test_client_setup_errors_become_controlled_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_credentials(*args: Any, **kwargs: Any) -> None:
        raise NoCredentialsError()

    monkeypatch.setattr("app.shared.adapters.llm.bedrock.boto3.client", no_credentials)

    with pytest.raises(LLMFailureError):
        list(BedrockProvider("us.test-model", "us-east-1", 30).stream(REQUEST))
