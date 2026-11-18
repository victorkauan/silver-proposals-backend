# Content and versions

A proposal's `content` (Markdown) changes only through the endpoints below and AI generation. Every change creates a
**version**, so the history is complete and never rewritten.

| Method and path | Minimum role | Success |
|---|---|---|
| `PUT /proposals/{id}/content` | editor | `200` proposal with the new `content` and `version` |
| `GET /proposals/{id}/versions?limit=20&offset=0` | viewer | `200` `{ "items": [...], "total": n }`, newest first |
| `GET /proposals/{id}/versions/{number}` | viewer | `200` version, including `content` |
| `POST /proposals/{id}/versions/{number}/restore` | editor | `200` proposal; the old content becomes a **new** version |

Non-members get `404 proposal_not_found`, and viewers get `403 forbidden` on save and restore.

## Saving content

```json
PUT /proposals/{id}/content
{ "content": "# Proposta\n...", "base_version": 3 }
```

`base_version` is the `version` the client loaded. If the proposal changed since then, the API answers
`409 version_conflict` and keeps the newer content, so the client can reload instead of overwriting someone else's work.
The check runs under a row lock, so two simultaneous saves cannot both succeed. Saving content identical to the current
content creates no version. `content` is limited to 200,000 characters.

## Version fields

| Field | Notes |
|---|---|
| `number` | 1, 2, 3, … per proposal; the proposal's `version` is the latest number (0 before any content) |
| `source` | `generated` (AI generation), `edited` (saved by a user), or `restored` (copied from an older version) |
| `author_name` | name of the user who created the version, or null if the account was deleted |
| `content_chars` | length of the content |
| `created_at` | timestamp |
| `content` | only in `GET /versions/{number}` |
