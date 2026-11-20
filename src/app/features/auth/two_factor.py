import hashlib
import hmac
import os
import re
import secrets
import uuid
from datetime import UTC, datetime

import pyotp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.shared.config import get_settings

ISSUER = "Silver Proposals"
RECOVERY_CODE_COUNT = 10
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
_NONCE_BYTES = 12
_TOTP_CODE = re.compile(r"[0-9]{6}")


def _aad(user_id: uuid.UUID) -> bytes:
    # Binds each ciphertext to its user, so a secret copied to another row fails to decrypt.
    return b"totp:" + user_id.bytes


def encrypt_secret(user_id: uuid.UUID, secret: str) -> bytes:
    nonce = os.urandom(_NONCE_BYTES)
    return nonce + AESGCM(get_settings().totp_key).encrypt(nonce, secret.encode(), _aad(user_id))


def decrypt_secret(user_id: uuid.UUID, blob: bytes) -> str:
    nonce, ciphertext = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    return AESGCM(get_settings().totp_key).decrypt(nonce, ciphertext, _aad(user_id)).decode()


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def is_totp_code(code: str) -> bool:
    return _TOTP_CODE.fullmatch(code) is not None


def match_totp(
    secret: str, code: str, last_step: int | None, now: datetime | None = None
) -> int | None:
    if not is_totp_code(code):
        return None
    totp = pyotp.TOTP(secret)
    current = totp.timecode(now or datetime.now(UTC))
    # One step of drift either way (RFC 6238, section 5.2); a used step is never accepted again.
    for step in (current - 1, current, current + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(totp.generate_otp(step), code):
            return step
    return None


def new_recovery_codes() -> list[str]:
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def normalize_recovery_code(code: str) -> str:
    return re.sub(r"[^a-z0-9]", "", code.lower())


def hash_recovery_code(code: str) -> str:
    # Keyed hash: a database dump alone is not enough to brute-force the ~49-bit codes offline.
    key = hashlib.sha256(b"recovery-codes:" + get_settings().totp_key).digest()
    return hmac.new(key, normalize_recovery_code(code).encode(), hashlib.sha256).hexdigest()
