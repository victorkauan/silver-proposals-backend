from collections.abc import Iterator
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, ConnectTimeoutError, ReadTimeoutError

from app.shared.adapters.llm.base import (
    GenerationRequest,
    LLMFailureError,
    LLMTimeoutError,
    LLMUnavailableError,
    StreamEvent,
    TextDelta,
    Usage,
)

if TYPE_CHECKING:
    from types_boto3_bedrock_runtime import BedrockRuntimeClient

_UNAVAILABLE = {
    "throttlingexception",
    "serviceunavailableexception",
    "servicequotaexceededexception",
}
_TIMEOUT = {"modeltimeoutexception"}


class BedrockProvider:
    def __init__(
        self,
        model: str,
        region: str,
        read_timeout_seconds: int,
        client: "BedrockRuntimeClient | None" = None,
    ) -> None:
        self.model = model
        self._region = region
        self._read_timeout_seconds = read_timeout_seconds
        self._client = client

    def _get_client(self) -> "BedrockRuntimeClient":
        if self._client is None:
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self._region,
                config=Config(
                    connect_timeout=5,
                    read_timeout=self._read_timeout_seconds,
                    retries={"max_attempts": 3, "mode": "adaptive"},
                ),
            )
        return self._client

    def stream(self, request: GenerationRequest) -> Iterator[StreamEvent]:
        try:
            response = self._get_client().converse_stream(
                modelId=self.model,
                system=[{"text": request.system}],
                messages=[{"role": "user", "content": [{"text": request.prompt}]}],
                inferenceConfig={
                    "maxTokens": request.max_tokens,
                    "temperature": request.temperature,
                },
            )
            for event in response["stream"]:
                if "contentBlockDelta" in event:
                    text = event["contentBlockDelta"]["delta"].get("text")
                    if text:
                        yield TextDelta(text)
                elif "metadata" in event:
                    usage = event["metadata"]["usage"]
                    yield Usage(usage["inputTokens"], usage["outputTokens"])
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "").lower()
            if code in _UNAVAILABLE:
                raise LLMUnavailableError(code) from exc
            if code in _TIMEOUT:
                raise LLMTimeoutError(code) from exc
            raise LLMFailureError(code or "client_error") from exc
        except (ReadTimeoutError, ConnectTimeoutError) as exc:
            raise LLMTimeoutError(type(exc).__name__) from exc
        except BotoCoreError as exc:
            raise LLMFailureError(type(exc).__name__) from exc
