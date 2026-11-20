# Account and personal data

Endpoints for the signed-in user to manage the account and exercise the data subject's rights under the LGPD
(Lei 13.709/2018, art. 18). All of them need `Authorization: Bearer`.

## Endpoints

| Method and path | Rate limit (per IP) | Body | Success | Errors |
|---|---|---|---|---|
| `PATCH /account` | none | `{ "name": "..." }` | `200` user | `422 validation_error` |
| `PUT /account/email` | 5 per minute | `{ "email": "...", "password": "..." }` | `200` user | `403 invalid_password`, `409 email_taken`, `422`, `429` |
| `POST /account/privacy-acceptance` | none | none | `200` user | none |
| `GET /account/export` | 3 per minute | none | `200` JSON attachment | `429` |
| `POST /account/delete` | 3 per minute | `{ "password": "..." }` | `204` and the refresh cookie is cleared | `403 invalid_password`, `422`, `429` |

Changing the e-mail and deleting the account ask for the current password, so a stolen access token alone cannot take
over or erase the account.

## Privacy notice

Sign-up requires `"accept_privacy": true`. The user stores the accepted notice version (`privacy_version`) and the time
(`privacy_accepted_at`); the current version is `PRIVACY_NOTICE_VERSION` in `features/auth/models.py`. The user response
carries `privacy_up_to_date`, so the frontend asks users who accepted an older version, or none, to accept the current one.
When the notice text changes, bump the version.

## Data export

`GET /account/export` returns `silver-proposals-dados.json` with `Cache-Control: no-store`:

| Key | Content |
|---|---|
| `account` | id, e-mail, name, creation and update times, accepted notice version and time, when 2FA was turned on |
| `sessions` | session start, browser (`User-Agent`), creation, expiry, use, and revocation times of each refresh token (no hashes) |
| `proposals` | every proposal the user is a member of, with the user's role, briefing, and current content |
| `authored_versions` | every version the user wrote, with its content |
| `share_links_created` | proposal, creation, expiry, and revocation times of the links the user created (no tokens or hashes) |

Password and token hashes, the two-factor secret, and recovery-code hashes never leave the database.

## Account deletion

`POST /account/delete` runs in one transaction:

1. Proposals where the user is the **only owner** are deleted, with their members, versions, and share links.
2. The user is deleted. Memberships and refresh tokens cascade. Versions the user wrote and links the user created stay
   in proposals that other people still own, with the author set to null, so their history is kept without personal data.

The log records `account_deleted` with the number of proposals removed, and no e-mail or name.

## Refresh token cleanup

Expired refresh tokens are deleted every `TOKEN_PURGE_INTERVAL_MINUTES` (default 360) by a task inside the API process,
and once at startup (`refresh_tokens_purged` in the logs, with the count). Revoked and rotated tokens stay until they
expire, because reuse detection needs them until then; no token row outlives its 7-day lifetime by more than one interval.
`0` turns the task off (tests).
