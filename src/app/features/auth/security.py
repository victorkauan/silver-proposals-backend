import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.shared.config import get_settings

ALGORITHM = "HS256"
CHALLENGE_TTL = timedelta(minutes=5)

_hasher = PasswordHasher()
# Verified against unknown e-mails so a login takes the same time whether or not the account exists.
_DUMMY_HASH = _hasher.hash("timing-equalizer-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def burn_password_check(password: str) -> None:
    verify_password(_DUMMY_HASH, password)


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID


def _encode(payload: dict[str, Any], ttl: timedelta, now: datetime | None) -> str:
    issued_at = now or datetime.now(UTC)
    claims = {**payload, "iat": issued_at, "exp": issued_at + ttl}
    return jwt.encode(claims, get_settings().jwt_secret, algorithm=ALGORITHM)


def _decode(token: str, token_type: str, required: list[str]) -> dict[str, Any] | None:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "exp", "iat", *required]},
        )
    except jwt.InvalidTokenError:
        return None
    return payload if payload.get("type") == token_type else None


def create_access_token(
    user_id: uuid.UUID, session_id: uuid.UUID, now: datetime | None = None
) -> str:
    ttl = timedelta(minutes=get_settings().access_token_ttl_minutes)
    payload = {"sub": str(user_id), "sid": str(session_id), "type": "access"}
    return _encode(payload, ttl, now)


def decode_access_token(token: str) -> AccessClaims | None:
    payload = _decode(token, "access", ["sid"])
    if payload is None:
        return None
    try:
        return AccessClaims(uuid.UUID(payload["sub"]), uuid.UUID(payload["sid"]))
    except ValueError:
        return None


@dataclass(frozen=True)
class ChallengeClaims:
    user_id: uuid.UUID
    credentials: str


def challenge_credentials(password_hash: str, totp_secret: bytes) -> str:
    return hmac.new(
        get_settings().jwt_secret.encode(),
        b"two-factor-credentials:" + password_hash.encode() + b"\0" + totp_secret,
        hashlib.sha256,
    ).hexdigest()


def create_challenge_token(
    user_id: uuid.UUID, credentials: str, now: datetime | None = None
) -> str:
    payload = {"sub": str(user_id), "type": "two_factor", "credentials": credentials}
    return _encode(payload, CHALLENGE_TTL, now)


def decode_challenge_token(token: str) -> ChallengeClaims | None:
    payload = _decode(token, "two_factor", ["credentials"])
    if payload is None or not isinstance(payload["credentials"], str):
        return None
    try:
        return ChallengeClaims(uuid.UUID(payload["sub"]), payload["credentials"])
    except ValueError:
        return None


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
