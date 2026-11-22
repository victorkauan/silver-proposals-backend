import json
from collections.abc import Callable, Iterator
from typing import IO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.shared.adapters.llm.base import (
    GenerationRequest,
    LLMFailureError,
    LLMTimeoutError,
    LLMUnavailableError,
    StreamEvent,
    TextDelta,
    Usage,
)

Opener = Callable[[Request, float], IO[bytes]]

_UNAVAILABLE = {429, 500, 502, 503}
_TIMEOUT = {504}


def _open(request: Request, timeout: float) -> IO[bytes]:
    response: IO[bytes] = urlopen(request, timeout=timeout)  # noqa: S310 - __init__ only accepts https URLs
    return response


class DeepInfraProvider:
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        read_timeout_seconds: int,
        opener: Opener = _open,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("the DeepInfra base URL must use https")
        self.model = model
        self._api_key = api_key
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._read_timeout_seconds = read_timeout_seconds
        self._open = opener

    def _request(self, request: GenerationRequest) -> Request:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        return Request(  # noqa: S310 - __init__ only accepts https URLs
            self._url,
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            method="POST",
        )

    def stream(self, request: GenerationRequest) -> Iterator[StreamEvent]:
        try:
            with self._open(self._request(request), self._read_timeout_seconds) as response:
                for raw in response:
                    line = raw.decode().strip()
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    for choice in chunk.get("choices") or []:
                        text = (choice.get("delta") or {}).get("content")
                        if text:
                            yield TextDelta(text)
                    usage = chunk.get("usage")
                    if usage:
                        yield Usage(usage["prompt_tokens"], usage["completion_tokens"])
        except HTTPError as exc:
            code = f"http_{exc.code}"
            if exc.code in _UNAVAILABLE:
                raise LLMUnavailableError(code) from exc
            if exc.code in _TIMEOUT:
                raise LLMTimeoutError(code) from exc
            raise LLMFailureError(code) from exc
        except TimeoutError as exc:
            raise LLMTimeoutError("timeout") from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise LLMTimeoutError("timeout") from exc
            raise LLMUnavailableError("connection_error") from exc
        except (json.JSONDecodeError, KeyError) as exc:
            raise LLMFailureError("invalid_response") from exc
