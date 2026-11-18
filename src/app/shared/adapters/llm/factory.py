from functools import lru_cache

from app.shared.adapters.llm.base import LLMProvider
from app.shared.adapters.llm.bedrock import BedrockProvider
from app.shared.adapters.llm.fake import FakeProvider
from app.shared.config import get_settings


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.ai_provider == "bedrock":
        return BedrockProvider(
            settings.bedrock_model_id,
            settings.bedrock_region,
            settings.bedrock_read_timeout_seconds,
        )
    return FakeProvider()
