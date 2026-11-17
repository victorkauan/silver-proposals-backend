import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from testcontainers.community.postgres import PostgresContainer

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost:1/unused")
os.environ.setdefault("JWT_SECRET", "test-only-secret-with-at-least-32-characters")

from app.main import app
from app.shared.config import get_settings
from app.shared.db import get_engine, get_session_factory
from app.shared.rate_limit import storage

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def clear_caches() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture(autouse=True)
def reset_rate_limits() -> None:
    storage.reset()


@pytest.fixture(scope="session")
def migrated_database() -> Iterator[str]:
    with (
        PostgresContainer("postgres:17-alpine", driver="psycopg") as postgres,
        pytest.MonkeyPatch.context() as patch,
    ):
        url = postgres.get_connection_url()
        patch.setenv("DATABASE_URL", url)
        clear_caches()
        command.upgrade(Config(str(ALEMBIC_INI)), "head")
        yield url
        get_engine().dispose()
        clear_caches()


@pytest.fixture
def database(migrated_database: str) -> Iterator[str]:
    yield migrated_database
    with get_engine().begin() as connection:
        connection.execute(text("TRUNCATE users, refresh_tokens CASCADE"))


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app, base_url="https://testserver")
    app.dependency_overrides.clear()
