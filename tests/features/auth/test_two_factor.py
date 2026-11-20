import uuid
from datetime import UTC, datetime, timedelta

import pyotp
import pytest
from cryptography.exceptions import InvalidTag

from app.features.auth import two_factor

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def test_secret_round_trips_and_is_not_stored_in_clear() -> None:
    user_id = uuid.uuid4()
    secret = two_factor.new_secret()

    blob = two_factor.encrypt_secret(user_id, secret)

    assert secret.encode() not in blob
    assert two_factor.decrypt_secret(user_id, blob) == secret
    assert two_factor.encrypt_secret(user_id, secret) != blob


def test_secret_copied_to_another_user_does_not_decrypt() -> None:
    blob = two_factor.encrypt_secret(uuid.uuid4(), two_factor.new_secret())

    with pytest.raises(InvalidTag):
        two_factor.decrypt_secret(uuid.uuid4(), blob)


def test_provisioning_uri_names_the_issuer_and_account() -> None:
    uri = two_factor.provisioning_uri("JBSWY3DPEHPK3PXP", "ana@example.com")

    assert uri.startswith("otpauth://totp/Silver%20Proposals:ana%40example.com?")
    assert "secret=JBSWY3DPEHPK3PXP" in uri
    assert "issuer=Silver%20Proposals" in uri


@pytest.mark.parametrize("offset", [-30, 0, 30])
def test_codes_within_one_step_of_drift_are_accepted(offset: int) -> None:
    secret = two_factor.new_secret()
    code = pyotp.TOTP(secret).at(NOW + timedelta(seconds=offset))

    assert two_factor.match_totp(secret, code, None, NOW) is not None


def test_codes_outside_the_drift_window_are_rejected() -> None:
    secret = two_factor.new_secret()
    code = pyotp.TOTP(secret).at(NOW - timedelta(seconds=90))

    assert two_factor.match_totp(secret, code, None, NOW) is None


def test_a_used_step_is_never_accepted_again() -> None:
    secret = two_factor.new_secret()
    code = pyotp.TOTP(secret).at(NOW)

    step = two_factor.match_totp(secret, code, None, NOW)

    assert step is not None
    assert two_factor.match_totp(secret, code, step, NOW) is None


def test_recovery_codes_are_unique_and_readable() -> None:
    codes = two_factor.new_recovery_codes()

    assert len(codes) == two_factor.RECOVERY_CODE_COUNT
    assert len(set(codes)) == len(codes)
    assert all(len(code) == 11 and code[5] == "-" for code in codes)


def test_recovery_code_hash_ignores_case_and_separators() -> None:
    assert two_factor.hash_recovery_code("abcde-fghjk") == two_factor.hash_recovery_code(
        " ABCDE FGHJK "
    )
    assert two_factor.hash_recovery_code("abcde-fghjk") != two_factor.hash_recovery_code(
        "abcde-fghjm"
    )


def test_totp_code_shape() -> None:
    assert two_factor.is_totp_code("123456")
    assert not two_factor.is_totp_code("12345")
    assert not two_factor.is_totp_code("abcde-fghjk")
