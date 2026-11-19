# Observability

## Logs

The API writes one JSON object per line to standard output. In AWS, ECS sends it to the CloudWatch log group
`/ecs/silver-proposals-<env>-api`.

| Field | Always | Meaning |
|---|---|---|
| `timestamp`, `level`, `logger`, `event` | yes | ISO-8601 UTC time, `INFO`/`WARNING`/`ERROR`, logger name, event name |
| `request_id` | inside a request | the request's ID (see below) |
| `trace_id` | when tracing is on | X-Ray trace ID (`1-xxxxxxxx-...`), to jump from a log line to its trace |

Each request (except `/health` and `/ready`, which the load balancer and ECS call every few seconds) produces one
`request_completed` line:

```json
{"level": "INFO", "logger": "app.request", "event": "request_completed", "method": "GET",
 "route": "/public/proposals/{token}", "status": 200, "duration_ms": 21.0, "request_id": "4b6f..."}
```

- `route` is the **route template**, never the raw path, so share tokens and IDs never reach the logs. Uvicorn's
  access log is off (`--no-access-log`) for the same reason.
- Responses with status 500 or above are logged at `ERROR`. For streamed responses (generation), `duration_ms`
  covers the whole stream.
- Generation adds `generation_completed` (model, latency, tokens) or `generation_failed` (error code); see
  [Proposal generation](generation.md). Briefings, proposal content, passwords, and tokens are never logged.

### Request ID

Every response carries `X-Request-ID`. A client may send its own (8 to 64 characters: letters, digits, `.`, `_`,
`-`); otherwise the API generates one. Search the logs for it to find every line of a request.

## Traces

With `OTEL_EXPORTER_OTLP_ENDPOINT` set, the API sends OpenTelemetry traces over OTLP/HTTP, with spans for
incoming requests (FastAPI), database queries (SQLAlchemy), and AWS calls (botocore, which includes each
Bedrock invocation). Trace IDs use the X-Ray format and the X-Ray propagator. In AWS, a collector sidecar in the
same task receives them and sends them to AWS X-Ray. Without the variable, tracing is off (local runs and tests).

| Variable | Example | Meaning |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318` | collector endpoint; enables tracing |
| `OTEL_SERVICE_NAME` | `silver-proposals-api-staging` | service name in X-Ray (default `silver-proposals-api`) |

Health checks are excluded from traces.
