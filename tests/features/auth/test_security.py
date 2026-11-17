import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.features.auth import security
from app.shared.config import get_settings


def test_password_hash_uses_argon2id_and_verifies() -> None:
    password_hash = security.hash_password("correct horse battery")

    assert password_hash.startswith("$argon2id$")
    assert security.verify_password(password_hash, "correct horse battery")
    assert not security.verify_password(password_hash, "wrong password")


def test_verify_password_rejects_malformed_hash() -> None:
    assert not security.verify_password("not-a-hash", "anything")


def test_access_token_round_trip() -> None:
    user_id = uuid.uuid4()

    assert security.decode_access_token(security.create_access_token(user_id)) == user_id


def test_expired_access_token_is_rejected() -> None:
    issued = datetime.now(UTC) - timedelta(hours=1)

    assert security.decode_access_token(security.create_access_token(uuid.uuid4(), issued)) is None


def test_token_signed_with_another_secret_is_rejected() -> None:
    forged = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "another-secret-with-at-least-32-characters",
        algorithm="HS256",
    )

    assert security.decode_access_token(forged) is None


def test_token_with_wrong_type_is_rejected() -> None:
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "refresh",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        get_settings().jwt_secret,
        algorithm="HS256",
    )

    assert security.decode_access_token(token) is None


def test_refresh_tokens_are_random_and_hashed() -> None:
    first, second = security.new_refresh_token(), security.new_refresh_token()

    assert first != second
    assert len(security.hash_refresh_token(first)) == 64
    assert security.hash_refresh_token(first) != first
