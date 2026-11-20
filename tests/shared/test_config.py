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
