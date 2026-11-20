import time
from typing import Any

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.features.auth.models import RecoveryCode, User
from app.shared.db import get_session_factory
from app.shared.rate_limit import storage

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("database")]

EMAIL = "ana@example.com"
PASSWORD = "uma senha longa"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def signup(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={"email": EMAIL, "name": "Ana", "password": PASSWORD, "accept_privacy": True},
        headers={"User-Agent": "Firefox no Linux"},
    )
    assert response.status_code == 201
    return bearer(response.json()["access_token"])


def login(client: TestClient, password: str = PASSWORD, agent: str = "Chrome") -> Any:
    return client.post(
        "/auth/login", json={"email": EMAIL, "password": password}, headers={"User-Agent": agent}
    )


def next_code(secret: str) -> str:
    # The step used to enable 2FA is spent, so tests use the next one to avoid a replay.
    return pyotp.TOTP(secret).at(int(time.time()) + 30)


def enable_two_factor(client: TestClient, headers: dict[str, str]) -> tuple[str, list[str]]:
    setup = client.post("/account/two-factor/setup", headers=headers, json={"password": PASSWORD})
    assert setup.status_code == 200
    secret: str = setup.json()["secret"]
    enabled = client.post(
        "/account/two-factor/enable", headers=headers, json={"code": pyotp.TOTP(secret).now()}
    )
    assert enabled.status_code == 200
    codes: list[str] = enabled.json()["codes"]
    return secret, codes


def challenge(client: TestClient) -> str:
    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["two_factor_required"] is True
    assert "access_token" not in body
    assert "set-cookie" not in response.headers
    token: str = body["challenge_token"]
    return token


def test_two_factor_starts_disabled(client: TestClient) -> None:
    headers = signup(client)

    response = client.get("/account/two-factor", headers=headers)

    assert response.json() == {
        "enabled": False,
        "enabled_at": None,
        "recovery_codes_remaining": 0,
    }
    assert client.get("/auth/me", headers=headers).json()["two_factor_enabled"] is False


def test_setup_requires_the_password(client: TestClient) -> None:
    headers = signup(client)

    response = client.post("/account/two-factor/setup", headers=headers, json={"password": "x"})

    assert response.status_code == 403
    assert response.json()["code"] == "invalid_password"


def test_setup_returns_an_authenticator_uri(client: TestClient) -> None:
    headers = signup(client)

    body = client.post(
        "/account/two-factor/setup", headers=headers, json={"password": PASSWORD}
    ).json()

    assert body["otpauth_uri"].startswith("otpauth://totp/Silver%20Proposals:ana%40example.com")
    assert f"secret={body['secret']}" in body["otpauth_uri"]


def test_enable_without_setup_is_rejected(client: TestClient) -> None:
    headers = signup(client)

    response = client.post("/account/two-factor/enable", headers=headers, json={"code": "123456"})

    assert response.status_code == 409
    assert response.json()["code"] == "two_factor_setup_required"


def test_enable_rejects_a_wrong_code(client: TestClient) -> None:
    headers = signup(client)
    client.post("/account/two-factor/setup", headers=headers, json={"password": PASSWORD})

    response = client.post("/account/two-factor/enable", headers=headers, json={"code": "000000"})

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_two_factor_code"


def test_enable_stores_the_secret_encrypted_and_codes_hashed(client: TestClient) -> None:
    headers = signup(client)

    secret, codes = enable_two_factor(client, headers)

    assert len(codes) == 10
    with get_session_factory()() as session:
        user = session.scalars(select(User)).one()
        hashes = session.scalars(select(RecoveryCode.code_hash)).all()
    assert user.totp_secret is not None
    assert secret.encode() not in user.totp_secret
    assert user.totp_pending_secret is None
    assert len(hashes) == 10
    assert not set(codes) & set(hashes)
    status = client.get("/account/two-factor", headers=headers).json()
    assert status["enabled"] is True
    assert status["recovery_codes_remaining"] == 10
    assert (
        client.post(
            "/account/two-factor/setup", headers=headers, json={"password": PASSWORD}
        ).json()["code"]
        == "two_factor_already_enabled"
    )


def test_login_with_two_factor_needs_a_code(client: TestClient) -> None:
    secret, _ = enable_two_factor(client, signup(client))
    token = challenge(client)

    wrong = client.post("/auth/login/two-factor", json={"challenge_token": token, "code": "000000"})
    right = client.post(
        "/auth/login/two-factor", json={"challenge_token": token, "code": next_code(secret)}
    )

    assert wrong.status_code == 401
    assert wrong.json()["code"] == "invalid_two_factor_code"
    assert right.status_code == 200
    assert right.json()["user"]["two_factor_enabled"] is True
    assert "refresh_token=" in right.headers["set-cookie"]


def test_a_totp_code_cannot_be_replayed(client: TestClient) -> None:
    secret, _ = enable_two_factor(client, signup(client))
    code = next_code(secret)

    first = client.post(
        "/auth/login/two-factor", json={"challenge_token": challenge(client), "code": code}
    )
    replay = client.post(
        "/auth/login/two-factor", json={"challenge_token": challenge(client), "code": code}
    )

    assert first.status_code == 200
    assert replay.status_code == 401


def test_a_recovery_code_works_once(client: TestClient) -> None:
    headers = signup(client)
    _, codes = enable_two_factor(client, headers)
    code = codes[0].upper().replace("-", " ")

    first = client.post(
        "/auth/login/two-factor", json={"challenge_token": challenge(client), "code": code}
    )
    again = client.post(
        "/auth/login/two-factor", json={"challenge_token": challenge(client), "code": code}
    )

    assert first.status_code == 200
    assert again.status_code == 401
    status = client.get("/account/two-factor", headers=headers).json()
    assert status["recovery_codes_remaining"] == 9


def test_an_invalid_challenge_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/auth/login/two-factor", json={"challenge_token": "forged", "code": "123456"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_challenge"


def test_an_access_token_is_not_a_challenge(client: TestClient) -> None:
    headers = signup(client)
    enable_two_factor(client, headers)
    access = headers["Authorization"].removeprefix("Bearer ")

    response = client.post(
        "/auth/login/two-factor", json={"challenge_token": access, "code": "123456"}
    )

    assert response.json()["code"] == "invalid_challenge"


def test_two_factor_attempts_are_limited_per_ip(client: TestClient) -> None:
    enable_two_factor(client, signup(client))
    token = challenge(client)
    body = {"challenge_token": token, "code": "000000"}

    statuses = [client.post("/auth/login/two-factor", json=body).status_code for _ in range(6)]

    assert statuses == [401] * 5 + [429]


def test_two_factor_attempts_are_limited_per_account(client: TestClient) -> None:
    enable_two_factor(client, signup(client))
    token = challenge(client)
    body = {"challenge_token": token, "code": "000000"}
    statuses = []
    for _ in range(11):
        # Clears only the per-IP counter each time, as if each guess came from a new address.
        for key in list(storage.events):
            if "two_factor_login" not in key:
                del storage.events[key]
        statuses.append(client.post("/auth/login/two-factor", json=body).status_code)

    assert statuses == [401] * 10 + [429]


def test_disable_needs_password_and_code(client: TestClient) -> None:
    headers = signup(client)
    secret, _ = enable_two_factor(client, headers)

    wrong_password = client.post(
        "/account/two-factor/disable",
        headers=headers,
        json={"password": "errada", "code": next_code(secret)},
    )
    wrong_code = client.post(
        "/account/two-factor/disable",
        headers=headers,
        json={"password": PASSWORD, "code": "000000"},
    )
    done = client.post(
        "/account/two-factor/disable",
        headers=headers,
        json={"password": PASSWORD, "code": next_code(secret)},
    )

    assert wrong_password.status_code == 403
    assert wrong_code.status_code == 400
    assert done.status_code == 204
    assert client.get("/account/two-factor", headers=headers).json()["enabled"] is False
    assert "access_token" in login(client).json()
    with get_session_factory()() as session:
        assert session.scalars(select(RecoveryCode)).all() == []


def test_disable_when_not_enabled_is_rejected(client: TestClient) -> None:
    headers = signup(client)

    response = client.post(
        "/account/two-factor/disable",
        headers=headers,
        json={"password": PASSWORD, "code": "123456"},
    )

    assert response.status_code == 409


def test_regenerating_recovery_codes_replaces_the_old_ones(client: TestClient) -> None:
    headers = signup(client)
    _, old = enable_two_factor(client, headers)

    response = client.post(
        "/account/two-factor/recovery-codes", headers=headers, json={"password": PASSWORD}
    )
    new = response.json()["codes"]
    with_old = client.post(
        "/auth/login/two-factor", json={"challenge_token": challenge(client), "code": old[0]}
    )

    assert response.status_code == 200
    assert len(new) == 10
    assert not set(old) & set(new)
    assert with_old.status_code == 401


def test_change_password_ends_other_sessions(client: TestClient) -> None:
    headers = signup(client)
    other = bearer(login(client).json()["access_token"])

    response = client.put(
        "/account/password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "outra senha longa"},
    )

    assert response.status_code == 200
    assert response.json() == {"revoked": 1}
    assert client.get("/auth/me", headers=other).status_code == 401
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert login(client).status_code == 401
    assert login(client, "outra senha longa").status_code == 200


def test_change_password_requires_the_current_one(client: TestClient) -> None:
    headers = signup(client)

    response = client.put(
        "/account/password",
        headers=headers,
        json={"current_password": "errada", "new_password": "outra senha longa"},
    )

    assert response.status_code == 403


def test_change_password_rejects_a_short_new_password(client: TestClient) -> None:
    headers = signup(client)

    response = client.put(
        "/account/password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "curta"},
    )

    assert response.status_code == 422


def test_sessions_are_listed_with_the_current_one_marked(client: TestClient) -> None:
    headers = signup(client)
    login(client, agent="Safari no iPhone")

    sessions = client.get("/account/sessions", headers=headers).json()

    assert len(sessions) == 2
    current = [s for s in sessions if s["current"]]
    assert len(current) == 1
    assert current[0]["user_agent"] == "Firefox no Linux"
    assert {s["user_agent"] for s in sessions} == {"Firefox no Linux", "Safari no iPhone"}


def test_refresh_keeps_the_session_and_its_start(client: TestClient) -> None:
    headers = signup(client)
    before = client.get("/account/sessions", headers=headers).json()

    refreshed = client.post("/auth/refresh", headers={"User-Agent": "Firefox 2"}).json()
    after = client.get("/account/sessions", headers=bearer(refreshed["access_token"])).json()

    assert len(after) == 1
    assert after[0]["id"] == before[0]["id"]
    assert after[0]["started_at"] == before[0]["started_at"]
    assert after[0]["user_agent"] == "Firefox 2"
    assert after[0]["current"] is True


def test_ending_a_session_invalidates_its_access_token_at_once(client: TestClient) -> None:
    headers = signup(client)
    other = bearer(login(client).json()["access_token"])
    target = next(
        s for s in client.get("/account/sessions", headers=headers).json() if not s["current"]
    )

    response = client.delete(f"/account/sessions/{target['id']}", headers=headers)

    assert response.status_code == 204
    assert client.get("/auth/me", headers=other).json()["code"] == "invalid_token"
    assert client.delete(f"/account/sessions/{target['id']}", headers=headers).status_code == 404


def test_a_user_cannot_end_another_users_session(client: TestClient) -> None:
    headers = signup(client)
    session_id = client.get("/account/sessions", headers=headers).json()[0]["id"]
    stranger = client.post(
        "/auth/register",
        json={
            "email": "bia@example.com",
            "name": "Bia",
            "password": PASSWORD,
            "accept_privacy": True,
        },
    ).json()["access_token"]

    response = client.delete(f"/account/sessions/{session_id}", headers=bearer(stranger))

    assert response.status_code == 404
    assert client.get("/auth/me", headers=headers).status_code == 200


def test_end_other_sessions_keeps_the_current_one(client: TestClient) -> None:
    headers = signup(client)
    login(client)
    login(client)

    response = client.post("/account/sessions/revoke-others", headers=headers)

    assert response.json() == {"revoked": 2}
    sessions = client.get("/account/sessions", headers=headers).json()
    assert [s["current"] for s in sessions] == [True]


def test_logout_invalidates_the_access_token(client: TestClient) -> None:
    headers = signup(client)

    client.post("/auth/logout")

    assert client.get("/auth/me", headers=headers).status_code == 401


def test_security_routes_require_authentication(client: TestClient) -> None:
    assert client.get("/account/two-factor").status_code == 401
    assert client.get("/account/sessions").status_code == 401
    assert client.post("/account/sessions/revoke-others").status_code == 401


def test_password_change_invalidates_an_outstanding_challenge(client: TestClient) -> None:
    headers = signup(client)
    _, codes = enable_two_factor(client, headers)
    token = challenge(client)

    assert (
        client.put(
            "/account/password",
            headers=headers,
            json={"current_password": PASSWORD, "new_password": "uma nova senha longa"},
        ).status_code
        == 200
    )
    response = client.post(
        "/auth/login/two-factor", json={"challenge_token": token, "code": codes[0]}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_challenge"
