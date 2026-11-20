# Authentication

Design decision: [ADR-0001](../adr/0001-refresh-token-in-httponly-cookie.md).

## Endpoints

| Method and path | Auth | Rate limit (per IP) | Success | Errors |
|---|---|---|---|---|
| `POST /auth/register` | none | 3 per minute | `201` token response and refresh cookie | `409 email_taken`, `422 validation_error`, `429 rate_limited` |
| `POST /auth/login` | none | 5 per minute | `200` token response and refresh cookie | `401 invalid_credentials`, `422`, `429` |
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
    "privacy_accepted_at": "2026-11-20T18:00:00Z"
  }
}
```

Profile, e-mail, data export, and account deletion are in [Account and personal data](account.md).

## Tokens

| | Access token | Refresh token |
|---|---|---|
| Format | JWT, HS256, claims `sub`, `type`, `iat`, `exp` | 32 random bytes, URL-safe base64 |
| Lifetime | 15 minutes (`ACCESS_TOKEN_TTL_MINUTES`) | 7 days (`REFRESH_TOKEN_TTL_DAYS`) |
| Transport | `Authorization: Bearer` header | cookie `refresh_token`: `HttpOnly; Secure; SameSite=Strict; Path=/auth` |
| Storage | client memory only | SHA-256 hash in `refresh_tokens` |

**Rotation and reuse detection.** Every refresh marks the presented token as used and issues a new one in the same family.
Presenting a used token again means it was copied, so every token of that family is revoked and the user has to log in again.
Logout revokes the family. Expired tokens are deleted periodically ([cleanup](account.md#refresh-token-cleanup)).

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
