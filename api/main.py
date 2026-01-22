"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.config import get_settings
from api.db.engine import create_db_and_tables
from api.middleware.exception_handlers import register_exception_handlers
from api.middleware.rate_limit import limiter
from api.middleware.security_headers import SecurityHeadersMiddleware
from api.routes import auth, calculate, health, invitations, opinions, projects, users


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

    # Rate limiting setup
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # Security headers middleware (added first, executes last)
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS middleware for frontend integration (restricted for security)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Accept", "Accept-Language"],
        max_age=600,  # Cache preflight requests for 10 minutes
    )

    # Register exception handlers (OCP: centralized error handling)
    register_exception_handlers(app)

    # Register routers
    app.include_router(health.router)
    app.include_router(calculate.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(projects.router)
    app.include_router(invitations.router)
    app.include_router(opinions.router)

    return app


app = create_app()
