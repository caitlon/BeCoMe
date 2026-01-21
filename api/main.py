"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.config import get_settings
from api.db.engine import create_db_and_tables
from api.middleware.exception_handlers import register_exception_handlers
from api.routes import auth, calculate, health, invitations, opinions, projects


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Initialize database tables on startup."""
    create_db_and_tables()
    yield


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Exception handling follows OCP: all API exceptions are handled
    centrally in middleware, routes don't need try-except blocks.
    """
    settings = get_settings()

    app = FastAPI(
        title="BeCoMe API",
        description="Best Compromise Mean — Group Decision Making under Fuzzy Uncertainty",
        version=settings.api_version,
        lifespan=lifespan,
    )

    # Register exception handlers (OCP: centralized error handling)
    register_exception_handlers(app)

    # Register routers
    app.include_router(health.router)
    app.include_router(calculate.router)
    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(invitations.router)
    app.include_router(opinions.router)

    return app


app = create_app()
