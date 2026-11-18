from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "staging", "prod"] = "local"
    database_url: str
    jwt_secret: str = Field(min_length=32)
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    cors_origins: list[str] = []
    ai_provider: Literal["fake", "bedrock"] = "fake"
    fake_provider_delay_ms: int = Field(default=0, ge=0, le=1000)
    bedrock_model_id: str = "us.amazon.nova-2-lite-v1:0"
    bedrock_region: str = "us-east-1"
    bedrock_read_timeout_seconds: int = 120
    generation_max_tokens: int = 4096


@lru_cache
def get_settings() -> Settings:
    return Settings()
