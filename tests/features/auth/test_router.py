from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.features.auth.models import RefreshToken, User
from app.shared.db import get_session_factory

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("database")]

USER: dict[str, Any] = {
    "email": "Ana@Example.com",
    "name": "Ana Lima",
    "password": "uma senha longa",
    "accept_privacy": True,
}


def register(client: TestClient, **overrides: Any) -> Any:
    return client.post("/auth/register", json={**USER, **overrides})


def login(client: TestClient, email: str = USER["email"], password: str = USER["password"]) -> Any:
    return client.post("/auth/login", json={"email": email, "password": password})


def refresh_cookie(client: TestClient) -> str:
    value = client.cookies.get("refresh_token")
    assert value is not None
    return value


def test_register_creates_user_and_starts_session(client: TestClient) -> None:
    response = register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert body["user"]["email"] == "ana@example.com"
    cookie = response.headers["set-cookie"]
    assert "refresh_token=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/auth" in cookie


def test_password_is_stored_as_argon2_hash(client: TestClient) -> None:
    register(client)

    with get_session_factory()() as session:
        user = session.scalars(select(User)).one()
    assert user.password_hash.startswith("$argon2id$")
    assert USER["password"] not in user.password_hash


def test_register_records_the_privacy_acceptance(client: TestClient) -> None:
    user = register(client).json()["user"]

    assert user["privacy_up_to_date"] is True
    assert user["privacy_accepted_at"] is not None


@pytest.mark.parametrize("accept", [False, None])
def test_register_requires_accepting_the_privacy_notice(client: TestClient, accept: Any) -> None:
    payload = {**USER, "accept_privacy": accept}
    if accept is None:
        del payload["accept_privacy"]

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "accept_privacy"


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    register(client)

    response = register(client, email="ANA@example.com")

    assert response.status_code == 409
    assert response.json()["code"] == "email_taken"


@pytest.mark.parametrize("password", ["", "curta"])
def test_register_rejects_empty_or_short_password(client: TestClient, password: str) -> None:
    response = register(client, password=password)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "Verifique os dados informados."
    assert body["details"][0]["field"] == "password"


def test_login_succeeds_with_valid_credentials(client: TestClient) -> None:
    register(client)

    response = login(client, email="ana@example.com")

    assert response.status_code == 200
    me = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"}
    )
    assert me.json()["name"] == "Ana Lima"


def test_login_with_wrong_password_and_unknown_email_look_the_same(client: TestClient) -> None:
    register(client)

    wrong_password = login(client, password="senha errada demais")
    unknown_email = login(client, email="ninguem@example.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert (
        wrong_password.json()
        == unknown_email.json()
        == {
            "code": "invalid_credentials",
            "message": "E-mail ou senha inválidos.",
        }
    )


def test_login_rejects_empty_password(client: TestClient) -> None:
    response = login(client, password="")

    assert response.status_code == 422


def test_refresh_rotates_the_refresh_token(client: TestClient) -> None:
    register(client)
    first = refresh_cookie(client)

    response = client.post("/auth/refresh")

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert refresh_cookie(client) != first


def test_reusing_a_rotated_refresh_token_revokes_the_session(client: TestClient) -> None:
    register(client)
    stolen = refresh_cookie(client)
    client.post("/auth/refresh")
    current = refresh_cookie(client)

    client.cookies.set("refresh_token", stolen, domain="testserver.local", path="/auth")
    replay = client.post("/auth/refresh")
    client.cookies.clear()
    client.cookies.set("refresh_token", current, domain="testserver.local", path="/auth")
    after_replay = client.post("/auth/refresh")

    assert replay.status_code == 401
    assert replay.json()["code"] == "invalid_refresh_token"
    assert after_replay.status_code == 401
    with get_session_factory()() as session:
        tokens = session.scalars(select(RefreshToken)).all()
    assert all(token.revoked_at is not None for token in tokens)


def test_refresh_without_cookie_is_rejected(client: TestClient) -> None:
    response = client.post("/auth/refresh")

    assert response.status_code == 401


def test_logout_revokes_the_session_and_clears_the_cookie(client: TestClient) -> None:
    register(client)
    token = refresh_cookie(client)

    response = client.post("/auth/logout")
    client.cookies.set("refresh_token", token, domain="testserver.local", path="/auth")
    refresh_after_logout = client.post("/auth/refresh")

    assert response.status_code == 204
    assert 'refresh_token=""' in response.headers["set-cookie"]
    assert refresh_after_logout.status_code == 401
    with get_session_factory()() as session:
        stored = session.scalars(select(RefreshToken)).one()
    assert stored.revoked_at is not None


def test_me_requires_a_token(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_rejects_an_invalid_token(client: TestClient) -> None:
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


def test_login_is_rate_limited(client: TestClient) -> None:
    statuses = [login(client, password="tentativa").status_code for _ in range(6)]

    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429
    assert login(client).json()["code"] == "rate_limited"
