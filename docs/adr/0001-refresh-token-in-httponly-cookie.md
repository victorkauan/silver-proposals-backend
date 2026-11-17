---
status: accepted
date: 2026-11-17
decision-makers: Victor Kauan
---

# Keep the refresh token in an httpOnly cookie and the access token in memory

## Context and Problem Statement

The single-page app at `app.silversoft.com.br` authenticates against the API at `api.silversoft.com.br`. Sessions use a
short-lived access token and a long-lived refresh token. Where should the browser keep each token so that a cross-site
scripting (XSS) bug or a cross-site request forgery (CSRF) cannot take over an account?

## Decision Drivers

- A stolen refresh token is worth days of access, while an access token is worth minutes.
- Any script running on the page can read `localStorage` and `sessionStorage`.
- App and API are on the same site (`silversoft.com.br`), but on different origins.

## Considered Options

- Both tokens in the response body, stored in `localStorage`
- Both tokens in cookies
- Access token in memory; refresh token in an `httpOnly` cookie

## Decision Outcome

Chosen option: **access token in memory, refresh token in an `httpOnly` cookie**.

- The access token (15 minutes) is returned in the response body. The app keeps it in a JavaScript variable and sends
  it as `Authorization: Bearer`. A page reload obtains a new one through `/auth/refresh`.
- The refresh token is an opaque random value in a cookie with `HttpOnly; Secure; SameSite=Strict; Path=/auth`. Scripts
  cannot read it, browsers send it only to `/auth/*` on same-site requests, and only over HTTPS.
- The database stores only the SHA-256 hash of each refresh token. Every refresh rotates it. Presenting an
  already-rotated token revokes the whole session family (reuse detection).

### Consequences

- Good, because XSS can at most use the access token for its remaining minutes and cannot steal the refresh token.
- Good, because `SameSite=Strict` stops other sites from triggering refresh or logout. Responses are not readable
  cross-origin, so a forged request would gain nothing anyway.
- Good, because a leaked database does not expose usable refresh tokens, since only hashes are stored.
- Bad, because the API must allow credentials in CORS for the app origin, which requires an explicit origin list.
- Bad, because the app must call `/auth/refresh` at startup to restore the session.

## Pros and Cons of the Options

### Both tokens in `localStorage`

- Good, because it is the simplest to implement.
- Bad, because any XSS steals a token that stays valid for days.

### Both tokens in cookies

- Good, because scripts cannot read them.
- Bad, because every API request becomes CSRF-relevant, which calls for CSRF tokens on all state-changing routes.

### Access token in memory, refresh token in an `httpOnly` cookie

- Good, because it balances XSS exposure (minutes) and CSRF exposure (only `/auth`, blocked by `SameSite=Strict`).
- Bad, because a session restore request is needed after every page load.

## More Information

- [Authentication reference](../reference/authentication.md)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
