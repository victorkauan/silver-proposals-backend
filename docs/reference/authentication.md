# Authentication

Design decisions: [ADR-0001](../adr/0001-refresh-token-in-httponly-cookie.md) (token storage) and
[ADR-0003](../adr/0003-totp-two-factor-and-revocable-sessions.md) (two-factor authentication and revocable sessions).

## Endpoints

| Method and path | Auth | Rate limit (per IP) | Success | Errors |
|---|---|---|---|---|
| `POST /auth/register` | none | 3 per minute | `201` token response and refresh cookie | `409 email_taken`, `422 validation_error`, `429 rate_limited` |
| `POST /auth/login` | none | 5 per minute | `200` token response and refresh cookie, or a [two-factor challenge](#two-factor-login) | `401 invalid_credentials`, `422`, `429` |
| `POST /auth/login/two-factor` | challenge token | 5 per minute per IP and 10 per 15 minutes per account | `200` token response and refresh cookie | `401 invalid_challenge`, `401 invalid_two_factor_code`, `422`, `429` |
| `POST /auth/refresh` | refresh cookie | 30 per minute | `200` token response and a **new** refresh cookie | `401 invalid_refresh_token`, `429` |
| `POST /auth/logout` | refresh cookie | none | `204` and the cookie is cleared | none |
| `GET /auth/me` | `Authorization: Bearer` | none | `200` user | `401 not_authenticated`, `401 invalid_token` |

Sign-up body: `{ "email", "name", "password", "accept_privacy": true }`; without the acceptance it returns `422`
([privacy notice](account.md#privacy-notice)).

Token response:

```json
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "<uuid>",
    "email": "ana@example.com",
    "name": "Ana Lima",
    "created_at": "2026-11-20T18:00:00Z",
    "privacy_up_to_date": true,
    "privacy_accepted_at": "2026-11-20T18:00:00Z",
    "two_factor_enabled": false
  }
}
```

Profile, e-mail, data export, and account deletion are in [Account and personal data](account.md). Two-factor setup,
password change, and the session list are in [Account security](security.md).

## Two-factor login

When the account has two-factor authentication (2FA) on, a correct password does **not** start a session. The login
returns a challenge instead, with no cookie:

```json
{ "two_factor_required": true, "challenge_token": "<JWT>", "expires_in": 300 }
```

The client then sends `POST /auth/login/two-factor` with `{ "challenge_token", "code" }`, where `code` is either the
6-digit code from the authenticator app or one of the recovery codes (case and separators are ignored). Success returns
the normal token response and refresh cookie.

- The challenge is a JWT with `type: "two_factor"`, valid for 5 minutes. It cannot be used as an access token, and an
  access token cannot be used as a challenge. A password change or a new authenticator invalidates outstanding challenges.
- TOTP codes follow RFC 6238 (SHA-1, 6 digits, 30-second steps) and accept one step of clock drift either way. The last
  accepted step is stored, so **a code is never accepted twice** (RFC 6238, section 5.2).
- A recovery code works once.
- Attempts are limited per IP (5 per minute) and per account (10 per 15 minutes), so spreading guesses over many
  addresses does not help.

## Tokens

| | Access token | Refresh token |
|---|---|---|
| Format | JWT, HS256, claims `sub`, `sid` (session), `type`, `iat`, `exp` | 32 random bytes, URL-safe base64 |
| Lifetime | 15 minutes (`ACCESS_TOKEN_TTL_MINUTES`) | 7 days (`REFRESH_TOKEN_TTL_DAYS`) |
| Transport | `Authorization: Bearer` header | cookie `refresh_token`: `HttpOnly; Secure; SameSite=Strict; Path=/auth` |
| Storage | client memory only | SHA-256 hash in `refresh_tokens` |

**Rotation and reuse detection.** Every refresh marks the presented token as used and issues a new one in the same family.
Presenting a used token again means it was copied, so every token of that family is revoked and the user has to log in again.
Logout revokes the family. Expired tokens are deleted periodically ([cleanup](account.md#refresh-token-cleanup)).

**Sessions.** A token family is a session; its ID is the access token's `sid` claim. Every authenticated request checks
that the session still has a live token, so logging out, ending a session in [Account security](security.md#sessions),
or changing the password locks that session out **at once**, not when the access token expires. The cost is one indexed
query per request. Access tokens without `sid` (issued before this check existed) are rejected, and the client refreshes.

## Passwords

- Hashed with **Argon2id** (`argon2-cffi` defaults, RFC 9106 profile). Hashes are upgraded on login when the parameters change.
- Length between 8 and 128 characters, with no composition rules (NIST SP 800-63B).
- Wrong password and unknown e-mail return the same `401 invalid_credentials`. Unknown e-mails are checked against a dummy
  hash, so response time does not reveal whether an account exists.
- E-mails are stored lowercase.

## Rate limiting

Limits use a moving window per client IP, stored in memory. Two consequences:

- With several API tasks, each task counts on its own, so the effective limit grows with the number of tasks.
- Behind a load balancer, the client IP comes from `X-Forwarded-For`. Uvicorn must run with `--proxy-headers` and trust
  only the load balancer; otherwise every client shares the load balancer's address.
