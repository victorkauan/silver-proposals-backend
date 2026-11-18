from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.features.auth.router import router as auth_router
from app.features.generation.router import router as generation_router
from app.features.health.router import router as health_router
from app.features.proposals.router import router as proposals_router
from app.shared.config import get_settings
from app.shared.errors import register_error_handlers
from app.shared.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="Silver Proposals API", version="0.1.0")
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
    app.include_router(proposals_router)
    app.include_router(generation_router)
    return app


app = create_app()
