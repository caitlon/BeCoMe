"""FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.config import Environment, Settings, get_settings
from api.db.engine import create_db_and_tables, warm_up_connection_pool
from api.logging_config import setup_logging
from api.middleware.body_size import (
    BodySizeLimitMiddleware,
    RequestBodyTooLarge,
    body_too_large_handler,
)
from api.middleware.csrf import CSRFMiddleware
from api.middleware.exception_handlers import register_exception_handlers
from api.middleware.rate_limit import limiter, rate_limit_handler
from api.middleware.request_logging import RequestLoggingMiddleware
from api.middleware.security_headers import SecurityHeadersMiddleware
from api.routes import auth, calculate, health, invitations, opinions, projects, users

logger = logging.getLogger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Initialize database tables and log the application lifecycle.

    The startup and shutdown records carry the running version and active
    profile so the journal pins which build and environment served the run.
    """
    settings = get_settings()
    lifecycle = {"api_version": settings.api_version, "environment": settings.environment.value}

    create_db_and_tables()
    # Establish one live connection now so the first real request hits a warm pool
    # instead of paying the TCP + TLS + auth cost (a no-op for SQLite/test runs).
    warm_up_connection_pool()
    logger.info("Application started", extra={"event": "app_startup", **lifecycle})
    yield
    logger.info("Application stopped", extra={"event": "app_shutdown", **lifecycle})


def _init_sentry(settings: Settings) -> None:
    """Initialise Sentry error tracking when a DSN is configured.

    The FastAPI integration is auto-detected, so unhandled exceptions and
    request context are reported without extra wiring. A no-op when the DSN is
    unset, which keeps development and tests offline.

    :param settings: Application settings.
    """
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1,
            environment=settings.environment.value,
            # Never attach PII (client IP, cookies, headers, request bodies) to events.
            send_default_pii=False,
            # Frame locals are a separate switch that send_default_pii does not cover, and
            # they default to on. Auth handlers bind the parsed body to a local, so a fault
            # anywhere in the request would ship repr(ChangePasswordRequest) -- i.e. the
            # plaintext passwords, or a still-valid reset token -- to the tracker.
            include_local_variables=False,
        )


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Exception handling follows OCP: all API exceptions are handled
    centrally in middleware, routes don't need try-except blocks.
    """
    settings = get_settings()
    setup_logging(settings)
    _init_sentry(settings)

    # Hide interactive docs and the OpenAPI schema in production so the full API
    # surface (every route and schema) is not publicly enumerable.
    docs_hidden = settings.environment is Environment.PROD
    app = FastAPI(
        title="BeCoMe API",
        description="Best Compromise Mean — Group Decision Making under Fuzzy Uncertainty",
        version=settings.api_version,
        lifespan=lifespan,
        docs_url=None if docs_hidden else "/docs",
        redoc_url=None if docs_hidden else "/redoc",
        openapi_url=None if docs_hidden else "/openapi.json",
    )

    # Rate limiting setup
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestBodyTooLarge, body_too_large_handler)

    # Security headers middleware (added first, executes last)
    app.add_middleware(SecurityHeadersMiddleware)

    # Rate limiting: SlowAPIMiddleware enforces the limiter's default_limits on every
    # route, not just the @limiter.limit-decorated ones, so no endpoint is unthrottled.
    # It executes after CORS (CORS is added later, so it wraps this), letting preflight
    # OPTIONS be answered before any limit check.
    app.add_middleware(SlowAPIMiddleware)

    # CORS middleware for frontend integration (restricted for security)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "Accept",
            "Accept-Language",
            "X-Request-ID",
            "X-CSRF-Token",
        ],
        # allow_headers covers the request direction only. The SPA runs on a different
        # host than the API, so the CSRF token reaches it as a response header, and a
        # cross-origin response header stays invisible to JavaScript unless it is named
        # here (see api/auth/cookies.py::set_csrf_header).
        expose_headers=["X-CSRF-Token"],
        max_age=600,  # Cache preflight requests for 10 minutes
    )

    # CSRF double-submit check for cookie-authenticated mutations (no-op for Bearer clients).
    app.add_middleware(CSRFMiddleware)

    # Request/response logging with correlation IDs.
    app.add_middleware(RequestLoggingMiddleware)

    # Body-size guard (outermost: added last so it runs first and drops an over-large
    # request body before any other middleware buffers or logs it).
    app.add_middleware(BodySizeLimitMiddleware)

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
