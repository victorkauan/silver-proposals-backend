# Account security

Endpoints for the signed-in user to manage two-factor authentication (2FA), the password, and active sessions. All need
`Authorization: Bearer`. Design decision: [ADR-0003](../adr/0003-totp-two-factor-and-revocable-sessions.md). The login
side of 2FA is in [Authentication](authentication.md#two-factor-login).

## Endpoints

| Method and path | Rate limit (per IP) | Body | Success | Errors |
|---|---|---|---|---|
| `GET /account/two-factor` | none | none | `200` status | none |
| `POST /account/two-factor/setup` | 5 per minute | `{ "password" }` | `200` `{ "secret", "otpauth_uri" }` | `403 invalid_password`, `409 two_factor_already_enabled`, `429` |
| `POST /account/two-factor/enable` | 5 per minute | `{ "code" }` | `200` `{ "codes": [10 recovery codes] }` | `400 invalid_two_factor_code`, `409 two_factor_setup_required`, `409 two_factor_already_enabled`, `429` |
| `POST /account/two-factor/disable` | 5 per minute | `{ "password", "code" }` | `204` | `403 invalid_password`, `400 invalid_two_factor_code`, `409 two_factor_not_enabled`, `429` |
| `POST /account/two-factor/recovery-codes` | 5 per minute | `{ "password" }` | `200` `{ "codes": [...] }` (replaces the old ones) | `403 invalid_password`, `409 two_factor_not_enabled`, `429` |
| `PUT /account/password` | 5 per minute | `{ "current_password", "new_password" }` | `200` `{ "revoked": <other sessions ended> }` | `403 invalid_password`, `422`, `429` |
| `GET /account/sessions` | none | none | `200` list of sessions | none |
| `POST /account/sessions/revoke-others` | none | none | `200` `{ "revoked": <n> }` | none |
| `DELETE /account/sessions/{id}` | none | none | `204` | `404 session_not_found` |

Status: `{ "enabled": true, "enabled_at": "<time>", "recovery_codes_remaining": 9 }`.

## Two-factor authentication

1. **Setup** asks for the password, creates a new secret (160 bits, base32), stores it encrypted as *pending*, and
   returns it once with an `otpauth://` URI that the client shows as a QR code. Calling setup again replaces the pending
   secret.
2. **Enable** checks a code from the app against the pending secret. Only then 2FA is on, the step of that code is
   marked as used, and 10 recovery codes are returned **once**. The server keeps only their hashes, so they can never
   be shown again; the user can replace them.
3. **Disable** asks for the password and a current code (or a recovery code), then deletes the secret and the
   recovery codes.

Storage:

| Data | How it is stored |
|---|---|
| TOTP secret | AES-256-GCM with `TOTP_ENCRYPTION_KEY`, a random 96-bit nonce per encryption, and the user ID as associated data, so a ciphertext copied to another user's row does not decrypt |
| Recovery codes | 10 codes of 10 characters (`xxxxx-xxxxx`, an alphabet without look-alike characters, about 49 bits each), stored as HMAC-SHA256 with a key derived from `TOTP_ENCRYPTION_KEY`. A database dump alone is not enough to brute-force them |
| Last accepted TOTP step | `users.totp_last_step`, to refuse a replayed code |

## Password change

Asks for the current password; the new one follows the sign-up rules (8 to 128 characters). It ends **every other
session** and keeps the current one, so whoever may have used the old password elsewhere is locked out.

## Sessions

A session is a refresh-token family (see [Authentication](authentication.md#tokens)). Each item of the list:

```json
{
  "id": "<session uuid>",
  "started_at": "2026-11-20T18:00:00Z",
  "last_active_at": "2026-11-20T19:10:00Z",
  "expires_at": "2026-11-27T19:10:00Z",
  "user_agent": "Mozilla/5.0 ...",
  "current": true
}
```

`last_active_at` is the last login or token refresh, `user_agent` is the browser that did it (truncated to 255
characters). The client IP is **not** stored. Ending a session revokes its tokens, and its access token stops working on
the next request. A user can only end their own sessions; any other ID returns `404`.
