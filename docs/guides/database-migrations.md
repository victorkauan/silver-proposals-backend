# Database migrations

Migrations are managed with Alembic. They never run automatically on startup.

## Create a migration

1. Change or add models in `src/app/features/<feature>/models.py`, and register new models in `src/app/models.py`.
2. Start the database: `docker compose up -d db`, then bring it up to date with `uv run alembic upgrade head`.
3. Generate the revision: `uv run alembic revision --autogenerate -m "<what changes>"`. Ruff formats the new file
   automatically (post-write hooks in `alembic.ini`).
4. Review the generated file. Autogenerate misses some changes (renames, server defaults, data migrations), and it adds
   `# ### commands auto generated ###` markers that should be removed.
5. Test both directions:

   ```bash
   uv run alembic upgrade head
   uv run alembic downgrade -1
   uv run alembic upgrade head
   ```

The test suite builds its database by running every migration, so CI fails when a migration is broken.

## Apply migrations

```bash
uv run alembic upgrade head                        # from your machine
docker compose run --rm api alembic upgrade head   # inside the Compose stack
```
