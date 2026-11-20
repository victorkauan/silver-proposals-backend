# Configuration

Settings are read from environment variables, or from `.env` in local development. See `.env.example`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `ENVIRONMENT` | no | `local` | `local`, `staging`, or `prod` |
| `DATABASE_URL` | yes | | SQLAlchemy URL, for example `postgresql+psycopg://user:pass@host:5432/db` |
| `JWT_SECRET` | yes | | Secret that signs access tokens, at least 32 characters. Generate it with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. In AWS it comes from Secrets Manager. |
| `ACCESS_TOKEN_TTL_MINUTES` | no | `15` | Access token lifetime |
| `REFRESH_TOKEN_TTL_DAYS` | no | `7` | Refresh token lifetime |
| `CORS_ORIGINS` | no | `[]` | JSON list of origins allowed to call the API with credentials, for example `["http://localhost:5173"]` |
| `AI_PROVIDER` | no | `fake` | `fake` (no network) or `bedrock` |
| `FAKE_PROVIDER_DELAY_MS` | no | `0` | Pause before each word of the fake provider's stream, 0 to 1000. Use it locally to watch the generation UI; keep `0` in tests and CI |
| `BEDROCK_MODEL_ID` | no | `us.amazon.nova-2-lite-v1:0` | Bedrock model or inference profile ID. Amazon Nova models (for example `us.amazon.nova-pro-v1:0`, `us.amazon.nova-premier-v1:0`) are billed as Amazon Bedrock usage |
| `BEDROCK_REGION` | no | `us-east-1` | Region of the Bedrock runtime endpoint |
| `BEDROCK_READ_TIMEOUT_SECONDS` | no | `120` | Read timeout for the streaming connection |
| `GENERATION_MAX_TOKENS` | no | `4096` | Output token limit for each generation |
| `TOKEN_PURGE_INTERVAL_MINUTES` | no | `360` | How often expired refresh tokens are deleted; `0` turns the task off |

Tracing is configured with the standard OpenTelemetry variables (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`); see [Observability](observability.md).

The application fails at startup when a required variable is missing or invalid.
