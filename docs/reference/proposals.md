# Proposals

Every endpoint requires `Authorization: Bearer <access token>`. Proposal content is **Markdown**.

## Roles

Each proposal has members, and each member has one role. Creating a proposal makes you its owner.

| Action | Owner | Editor | Viewer | Not a member |
|---|---|---|---|---|
| Read (`GET /proposals/{id}`) | ✓ | ✓ | ✓ | `404` |
| Update metadata (`PATCH`) | ✓ | ✓ | `403` | `404` |
| Archive and restore | ✓ | `403` | `403` | `404` |
| Delete | ✓ | `403` | `403` | `404` |

Non-members get `404 proposal_not_found` instead of `403`, so they cannot learn whether a proposal exists.
Adding editors and viewers through invitations is planned for a later release.

## Endpoints

| Method and path | Minimum role | Success |
|---|---|---|
| `POST /proposals` | any user | `201` proposal (the caller becomes owner) |
| `GET /proposals?archived=false&q=&limit=20&offset=0` | any user | `200` `{ "items": [...], "total": n }`, newest first |
| `GET /proposals/{id}` | viewer | `200` proposal |
| `PATCH /proposals/{id}` | editor | `200` proposal; updates `title` and/or `client_name` |
| `POST /proposals/{id}/archive` | owner | `200` proposal with `archived_at` set |
| `POST /proposals/{id}/unarchive` | owner | `200` proposal with `archived_at` null |
| `DELETE /proposals/{id}` | owner | `204`, permanent |

The list returns archived proposals only when `archived=true`. `limit` accepts 1 to 100, and `total` counts every
match, so clients page with `offset`. `q` (up to 200 characters, trimmed) searches the title and the client name; it
ignores case and Portuguese accents, and `%` and `_` match literally. Accents are folded with SQL `translate`, so no
database extension is needed.

## Fields

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `title` | string | 1–200 characters, trimmed |
| `client_name` | string | 1–200 characters, trimmed |
| `briefing` | string | up to 10,000 characters; input for AI generation |
| `content` | string | Markdown document, empty until generated or edited |
| `version` | integer | number of the latest content version; 0 before any content |
| `role` | `owner`, `editor`, `viewer` | the caller's role on this proposal |
| `status` | `draft`, `generated`, `edited`, `shared`, `archived` | derived on each read, with the same rule as the [dashboard](dashboard.md); `shared` only for owners |
| `archived_at` | datetime or null | |
| `created_at`, `updated_at` | datetime | |

The list returns a summary without `briefing`, `content`, and `created_at`. `content` cannot be changed through
`PATCH`; it changes only through [content and versions](versions.md) and AI generation.
