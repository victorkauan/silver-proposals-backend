# Public share links

The owner of a proposal can create links that show it to anyone, without an account, until the link expires or is
revoked.

## Managing links (owner only)

| Method and path | Success |
|---|---|
| `POST /proposals/{id}/share-links` `{ "expires_in_days": 7 }` | `201` link **including `token`**; 1 to 90 days, default 7 |
| `GET /proposals/{id}/share-links` | `200` list with `id`, `expires_at`, `revoked_at`, `created_at`, `active` |
| `DELETE /proposals/{id}/share-links/{link_id}` | `204`; the link stops working immediately |

Editors and viewers get `403 forbidden`, and non-members get `404 proposal_not_found`. The **token is returned only once**,
when the link is created: the database stores only its SHA-256 hash, so a leaked database cannot be used to read
shared proposals. To share again, create a new link.

## Reading a shared proposal (public)

`POST /public/proposals/resolve` accepts `{"token":"..."}` without authentication. The request body keeps the token
out of the ALB request line. The legacy `GET /public/proposals/{token}` endpoint is deprecated and retained for
clients already using it. Both endpoints share a limit of 60 requests per minute per IP.

```json
{ "title": "...", "client_name": "...", "content": "# Proposta...", "updated_at": "..." }
```

- Only these four fields are returned: no briefing, IDs, members, or versions.
- `content` is the proposal's current content, so later edits appear on the link.
- Unknown, expired, revoked, and archived links all answer the same `404 share_link_not_found`
  ("Link inválido ou expirado."), so a request never reveals whether a link existed.
- Responses carry `Cache-Control: no-store` and `X-Robots-Tag: noindex`.

## Token and logs

Tokens are 32 random bytes (URL-safe base64, about 43 characters), so guessing one is not feasible. Because the token is
part of the URL, it could appear in access logs. The API never logs it: request logs use the route template, and
Uvicorn's access log is off. Load balancer access logs are disabled; if they are ever turned on, restrict access to
them. Keep expirations short.
