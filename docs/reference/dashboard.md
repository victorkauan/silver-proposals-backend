# Dashboard

`GET /dashboard/summary` requires an access token. It returns the signed-in user's dashboard with
`Cache-Control: no-store`. The API aggregates records across all relevant proposals, including ones beyond the list previews.

| Field | Meaning |
| --- | --- |
| `proposal_counts` | Exclusive counts for `draft`, `generated`, `edited`, `shared`, and `archived`, including zero counts |
| `generations_last_30_days` | Generated versions authored by the current user in the previous 30 days on proposals they can still access |
| `active_link_count` | Unexpired, unrevoked public links on unarchived proposals owned by the current user |
| `expiring_link_count` | Active links that expire in the next seven days |
| `recent_proposals` | Up to five proposals, most recently updated first, with the member's role and the effective status |
| `active_links` | Up to five owner-visible active links ordered by expiry, earliest first. Entries contain IDs, titles, and expiry dates |
| `recent_activity` | Up to eight version and share-link events, newest first. Entries contain the proposal, event type and timestamp, plus the version number when applicable |

The API derives proposal status in this order: archived; shared if the current user owns the proposal and it has an
active link; generated if the current version was generated; edited if it has another saved version; draft otherwise.
A restored version counts as edited. Editors and viewers see proposal and version metadata allowed by their membership.
Only owners see links or link events. Link entries include metadata only, and the public token remains available only at creation.

Link creation and revocation appear as separate events. Link events for archived proposals remain in the activity feed,
while their links are omitted from active counts because the public endpoint rejects archived proposals.
