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

The application fails at startup when a required variable is missing or invalid.
