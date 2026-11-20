import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.features.account.router import router as account_router
from app.features.auth.router import router as auth_router
from app.features.auth.service import purge_refresh_tokens
from app.features.generation.router import router as generation_router
from app.features.health.router import router as health_router
from app.features.proposals.router import router as proposals_router
from app.features.security.router import router as security_router
from app.features.sharing.router import router as sharing_router
from app.features.versions.router import router as versions_router
from app.shared.config import get_settings
from app.shared.db import get_session_factory
from app.shared.errors import register_error_handlers
from app.shared.logging import configure_logging
from app.shared.observability import RequestLogMiddleware, setup_tracing

logger = logging.getLogger("app.maintenance")


def purge_once() -> int:
    with get_session_factory()() as session:
        removed = purge_refresh_tokens(session)
    logger.info("refresh_tokens_purged", extra={"removed": removed})
    return removed


async def purge_periodically(interval_minutes: int) -> None:
    while True:
        try:
            await asyncio.to_thread(purge_once)
        except Exception:
            logger.exception("refresh_token_purge_failed")
        await asyncio.sleep(interval_minutes * 60)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    interval = get_settings().token_purge_interval_minutes
    task = asyncio.create_task(purge_periodically(interval)) if interval else None
    yield
    if task:
        task.cancel()


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="Silver Proposals API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(account_router)
    app.include_router(security_router)
    app.include_router(proposals_router)
    app.include_router(generation_router)
    app.include_router(versions_router)
    app.include_router(sharing_router)
    # Added last so it wraps everything, including CORS and error handlers.
    app.add_middleware(RequestLogMiddleware)
    setup_tracing(app, settings.environment)
    return app


app = create_app()
