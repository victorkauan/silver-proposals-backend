# Health checks

The API exposes two unauthenticated probes with different purposes.

| Endpoint | Probe | Checks | Success | Failure |
|---|---|---|---|---|
| `GET /health` | Liveness | Only that the process answers. Never touches the database. | `200 {"status": "ok"}` | No response |
| `GET /ready` | Readiness | Runs `SELECT 1` against PostgreSQL. | `200 {"status": "ready"}` | `503 {"status": "unavailable"}` |

## Why two probes

A database outage must stop traffic, not restart the API. If liveness depended on the database, the orchestrator
would replace every healthy task during an outage and make recovery slower.

- Use **`/health`** where a failure means "restart this container" (container health check).
- Use **`/ready`** where a failure means "send no traffic here" (load balancer target group health check).

Connections use `pool_pre_ping`, so `/ready` recovers on its own once the database is back. No restart is needed.
