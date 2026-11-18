import os
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from testcontainers.community.postgres import PostgresContainer

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost:1/unused")
os.environ.setdefault("JWT_SECRET", "test-only-secret-with-at-least-32-characters")

from app.features.auth.models import User
from app.features.auth.security import create_access_token
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
        connection.execute(
            text(
                "TRUNCATE users, refresh_tokens, proposals, proposal_members, proposal_versions,"
                " share_links"
                " CASCADE"
            )
        )


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app, base_url="https://testserver")
    app.dependency_overrides.clear()


@dataclass(frozen=True)
class AuthenticatedUser:
    id: uuid.UUID
    headers: dict[str, str]


@pytest.fixture
def make_user(database: str) -> Callable[[str], AuthenticatedUser]:
    def factory(name: str) -> AuthenticatedUser:
        with get_session_factory()() as session:
            user = User(email=f"{name}@example.com", name=name, password_hash="not-used")
            session.add(user)
            session.commit()
            token = create_access_token(user.id)
            return AuthenticatedUser(user.id, {"Authorization": f"Bearer {token}"})

    return factory
