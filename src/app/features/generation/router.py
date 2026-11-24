import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.features.auth.dependencies import CurrentUser
from app.features.generation.prompt import build_request
from app.features.generation.service import stream_generation
from app.features.proposals import service as proposals
from app.features.proposals.models import ProposalRole
from app.shared.adapters.llm.base import LLMProvider
from app.shared.adapters.llm.factory import get_llm_provider
from app.shared.config import get_settings
from app.shared.db import get_session
from app.shared.errors import AppError, ErrorCode
from app.shared.rate_limit import rate_limit

router = APIRouter(tags=["generation"])


@router.post(
    "/proposals/{proposal_id}/generate",
    summary="Generate the proposal content from its briefing (server-sent events)",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
    dependencies=[Depends(rate_limit("10/minute"))],
)
def generate(
    proposal_id: uuid.UUID,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> StreamingResponse:
    proposal = proposals.authorize(session, proposal_id, user.id, ProposalRole.EDITOR).proposal
    if not proposal.briefing.strip():
        raise AppError(ErrorCode.BRIEFING_REQUIRED, status.HTTP_422_UNPROCESSABLE_CONTENT)
    request = build_request(
        proposal.title,
        proposal.client_name,
        proposal.briefing,
        get_settings().generation_max_tokens,
    )
    user_id = user.id
    session.close()
    return StreamingResponse(
        stream_generation(provider, request, proposal_id, user_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
