---
status: accepted
date: 2026-11-20
decision-makers: Victor Kauan
---

# Offer TOTP two-factor authentication and make sessions revocable at once

## Context and Problem Statement

The threat model accepted "no multi-factor authentication for users" as a residual risk: a leaked or reused password
was enough to take over an account. Users also had no way to see where they were signed in or to sign out a lost
device. Access tokens are stateless JWTs that live 15 minutes, so revoking a refresh token did not stop a stolen access
token until it expired.

## Decision Drivers

- Close the account-takeover risk (OWASP Top 10:2025 A07, Authentication Failures) without extra cost or new providers.
- Keep the second-factor secret useless to someone who only gets a database dump or backup.
- Let users end a session and have it stop working right away.
- Free-plan AWS account: no paid services unless needed.

## Considered Options

Second factor:

- **TOTP** (RFC 6238) with authenticator apps
- SMS or e-mail one-time codes
- WebAuthn passkeys

Secret protection:

- **AES-256-GCM in the application, key in Secrets Manager**
- AWS KMS `Encrypt`/`Decrypt` per use
- Plain text (database encryption at rest only)

Session revocation:

- **Check the session on every authenticated request**
- Keep stateless access tokens and wait for expiry (up to 15 minutes)

## Decision Outcome

- **TOTP**, optional per user, with 10 single-use recovery codes. It works with any authenticator app, needs no
  messaging provider (SMS costs money and is open to SIM swapping), and is simple to verify. Passkeys are stronger
  (phishing-resistant) and remain a next step.
- **AES-256-GCM in the application** with `TOTP_ENCRYPTION_KEY`, a separate key stored in the same Secrets Manager
  secret as the JWT secret (no extra cost). The user ID is the associated data. KMS would add a network call per login
  and a monthly key cost for little gain at this size. Recovery codes are HMAC-SHA256 with a key derived from the same
  key, so they are useless without it.
- **The access token carries the session ID (`sid`)**, and every authenticated request checks that the session still
  has a live refresh token. This costs one indexed query per request and makes logout, "end session", and password
  change effective at once.

### Consequences

- Good: stolen passwords no longer give access to accounts with 2FA on; lost devices can be signed out.
- Good: a code is never accepted twice, and guesses are limited per IP and per account.
- Bad: losing `TOTP_ENCRYPTION_KEY` disables every enabled 2FA (users would need support to recover). The key is kept by
  Terraform in Secrets Manager and never rotated automatically.
- Bad: rate-limit counters live in memory per API task, so with several tasks the effective limit grows (see
  [Authentication](../reference/authentication.md#rate-limiting)).
- Neutral: every token issued before this change lacks `sid` and is refused once; the client refreshes silently.

## More Information

- RFC 6238, TOTP: https://www.rfc-editor.org/rfc/rfc6238
- NIST SP 800-63B, Digital Identity Guidelines (authenticators, replay resistance): https://pages.nist.gov/800-63-4/sp800-63b.html
- OWASP Multifactor Authentication Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html
- Reference: [Account security](../reference/security.md)
