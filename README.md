# Silver Proposals — Backend

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
- Docker (for the container image)

## Quick start

```bash
cp .env.example .env
uv sync
uv run uvicorn app.main:app --reload
```

The API listens on <http://localhost:8000>. The interactive docs are at `/docs`, and the liveness probe is at `/health`.

## Quality checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

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
