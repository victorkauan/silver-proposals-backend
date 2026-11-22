import pytest
from pydantic import ValidationError

from app.shared.config import Settings


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/app")

    settings = Settings(_env_file=None)

    assert settings.environment == "staging"
    assert settings.database_url == "postgresql+psycopg://user:pass@db:5432/app"


def test_settings_require_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("key", ["not base64!", "c2hvcnQ="])
def test_settings_reject_a_malformed_totp_key(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    monkeypatch.setenv("TOTP_ENCRYPTION_KEY", key)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_require_a_key_for_deepinfra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "deepinfra")
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)

    with pytest.raises(ValidationError, match="DEEPINFRA_API_KEY"):
        Settings(_env_file=None)


def test_settings_keep_the_deepinfra_key_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "deepinfra")
    monkeypatch.setenv("DEEPINFRA_API_KEY", "secret-key")

    settings = Settings(_env_file=None)

    assert settings.deepinfra_api_key is not None
    assert "secret-key" not in repr(settings)
