import base64
import binascii
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "staging", "prod"] = "local"
    database_url: str
    jwt_secret: str = Field(min_length=32)
    totp_encryption_key: str
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    cors_origins: list[str] = []
    ai_provider: Literal["fake", "bedrock", "deepinfra"] = "fake"
    fake_provider_delay_ms: int = Field(default=0, ge=0, le=1000)
    bedrock_model_id: str = "us.amazon.nova-2-lite-v1:0"
    bedrock_region: str = "us-east-1"
    bedrock_read_timeout_seconds: int = 120
    deepinfra_api_key: SecretStr | None = None
    deepinfra_model_id: str = "zai-org/GLM-5.3-Flash"
    deepinfra_base_url: str = "https://api.deepinfra.com/v1/openai"
    deepinfra_read_timeout_seconds: int = 120
    generation_max_tokens: int = 4096
    token_purge_interval_minutes: int = Field(default=360, ge=0)

    @field_validator("totp_encryption_key")
    @classmethod
    def _check_key(cls, value: str) -> str:
        try:
            key = base64.b64decode(value, validate=True)
        except binascii.Error as error:
            raise ValueError("must be base64") from error
        if len(key) != 32:
            raise ValueError("must decode to 32 bytes (AES-256)")
        return value

    @model_validator(mode="after")
    def _check_provider(self) -> "Settings":
        if self.ai_provider == "deepinfra" and not self.deepinfra_api_key:
            raise ValueError("DEEPINFRA_API_KEY is required when AI_PROVIDER is deepinfra")
        return self

    @property
    def totp_key(self) -> bytes:
        return base64.b64decode(self.totp_encryption_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
