import json
import logging
import time
import uuid
from collections.abc import Iterator
from typing import Any

from app.features.proposals.models import Proposal
from app.shared.adapters.llm.base import (
    GenerationRequest,
    LLMError,
    LLMProvider,
    LLMTimeoutError,
    LLMUnavailableError,
    TextDelta,
    Usage,
)
from app.shared.db import get_session_factory
from app.shared.errors import ErrorCode, error_body

logger = logging.getLogger(__name__)


def _event(name: str, payload: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def strip_code_fence(content: str) -> str:
    lines = content.strip().splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return content.strip()


def _error_code(exc: LLMError) -> ErrorCode:
    if isinstance(exc, LLMUnavailableError):
        return ErrorCode.GENERATION_UNAVAILABLE
    if isinstance(exc, LLMTimeoutError):
        return ErrorCode.GENERATION_TIMEOUT
    return ErrorCode.GENERATION_FAILED


def stream_generation(
    provider: LLMProvider, request: GenerationRequest, proposal_id: uuid.UUID
) -> Iterator[str]:
    started = time.monotonic()
    parts: list[str] = []
    usage: Usage | None = None
    context: dict[str, Any] = {"proposal_id": str(proposal_id), "model": provider.model}

    try:
        for event in provider.stream(request):
            if isinstance(event, TextDelta):
                parts.append(event.text)
                yield _event("delta", {"text": event.text})
            else:
                usage = event
    except LLMError as exc:
        code = _error_code(exc)
        logger.warning(
            "generation_failed",
            extra={
                **context,
                "error_code": code.value,
                "provider_error": str(exc),
                "latency_ms": round((time.monotonic() - started) * 1000),
            },
        )
        yield _event("error", error_body(code))
        return

    content = strip_code_fence("".join(parts))
    if not content:
        logger.warning("generation_failed", extra={**context, "error_code": "empty_output"})
        yield _event("error", error_body(ErrorCode.GENERATION_FAILED))
        return

    with get_session_factory()() as session:
        proposal = session.get(Proposal, proposal_id)
        if proposal is None:
            yield _event("error", error_body(ErrorCode.PROPOSAL_NOT_FOUND))
            return
        proposal.content = content
        session.commit()

    logger.info(
        "generation_completed",
        extra={
            **context,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "input_tokens": usage.input_tokens if usage else None,
            "output_tokens": usage.output_tokens if usage else None,
            "content_chars": len(content),
        },
    )
    yield _event("done", {"proposal_id": str(proposal_id)})
