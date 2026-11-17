# Silver Proposals — Backend

[![CI](https://github.com/victorkauan/silver-proposals-backend/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/victorkauan/silver-proposals-backend/actions/workflows/ci.yml)

REST API for **Silver Proposals**, an AI-powered SaaS for creating and managing commercial proposals.
Built with FastAPI, SQLAlchemy 2, Alembic, and PostgreSQL. It ships as a container image to Amazon ECR.

| Repository | Responsibility |
|---|---|
| **silver-proposals-backend** (this repo) | FastAPI API, container image published to ECR |
| [silver-proposals-frontend](https://github.com/victorkauan/silver-proposals-frontend) | React SPA, static build published to S3 + CloudFront |
| [silver-proposals-infra](https://github.com/victorkauan/silver-proposals-infra) | Terraform for AWS and Cloudflare |

Why three repositories: [ADR-0001](https://github.com/victorkauan/silver-proposals-infra/blob/main/docs/adr/0001-three-repositories.md).

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker with Compose (local database and container image)

## Local environment

### Full stack (API + PostgreSQL)

```bash
docker compose up --build
```

The API listens on <http://localhost:8000> (interactive docs at `/docs`, liveness probe at `/health`), and
PostgreSQL 17 on `localhost:5432`. Stop it with `docker compose down`, or add `-v` to also drop the database volume.

### Day-to-day development (hot reload)

Run only the database in Docker and the API on your machine:

```bash
cp .env.example .env
uv sync
docker compose up -d db
uv run uvicorn app.main:app --reload
```

### Migrations

Migrations never run automatically on startup. Apply them explicitly:

```bash
uv run alembic upgrade head                        # from your machine
docker compose run --rm api alembic upgrade head   # inside the stack
```

### With the frontend

Start the API with either option above, then follow the frontend's
[local setup](https://github.com/victorkauan/silver-proposals-frontend#with-the-local-api) with
`VITE_API_BASE_URL=http://localhost:8000`.

## Contributing

Install the Git hooks before your first commit:

```bash
uv tool install pre-commit
pre-commit install
```

Branch, commit, and pull request conventions are in [CONTRIBUTING.md](CONTRIBUTING.md).
Security issues: see [SECURITY.md](SECURITY.md).

## Quality checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

## Continuous integration

GitHub Actions runs on every pull request and on every push to `main`:

| Workflow | Job | Checks |
|---|---|---|
| [CI](.github/workflows/ci.yml) | `quality` | ruff (lint and format), mypy, pytest with coverage (minimum 80%) |
| | `build` | builds the container image |
| [PR title](.github/workflows/pr-title.yml) | `pr-title` | Conventional Commits title ending with `[SIL-<n>]` |

The coverage report is published in each run's summary.

## Container image

```bash
docker build -t silver-proposals-backend .
docker run --rm -p 8000:8000 --env-file .env silver-proposals-backend
```

## Layout

```
src/app/
  main.py         # application factory
  shared/         # cross-cutting code: configuration, database base, adapters
  features/       # one package per feature (router, schemas, service, repository, models)
migrations/       # Alembic environment and revisions
tests/            # mirrors src/app
```

## Documentation

See [docs/README.md](docs/README.md).
