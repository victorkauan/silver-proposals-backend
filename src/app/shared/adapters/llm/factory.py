from functools import lru_cache

from app.shared.adapters.llm.base import LLMProvider
from app.shared.adapters.llm.bedrock import BedrockProvider
from app.shared.adapters.llm.deepinfra import DeepInfraProvider
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
    if settings.ai_provider == "deepinfra" and settings.deepinfra_api_key:
        return DeepInfraProvider(
            settings.deepinfra_model_id,
            settings.deepinfra_api_key.get_secret_value(),
            settings.deepinfra_base_url,
            settings.deepinfra_read_timeout_seconds,
        )
    return FakeProvider(settings.fake_provider_delay_ms)
