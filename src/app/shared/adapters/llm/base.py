from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GenerationRequest:
    system: str
    prompt: str
    max_tokens: int
    temperature: float = 0.4


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int


StreamEvent = TextDelta | Usage


class LLMError(Exception):
    pass


class LLMUnavailableError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMFailureError(LLMError):
    pass


class LLMProvider(Protocol):
    @property
    def model(self) -> str: ...

    def stream(self, request: GenerationRequest) -> Iterator[StreamEvent]: ...
