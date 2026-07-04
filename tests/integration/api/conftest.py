"""Pytest fixtures and helpers for API integration tests."""

import os

# Select the test profile before importing api modules (settings are cached on first use)
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ["TESTING"] = "1"  # Must always be set; rate limiter reads it at import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from api.config import get_settings
from api.db.models import (  # noqa: F401 - models required for SQLModel.metadata.create_all
    CalculationResult,
    ExpertOpinion,
    Invitation,
    PasswordResetToken,
    Project,
    ProjectMember,
    User,
)
from api.db.session import get_session
from api.middleware.csrf import CSRFMiddleware
from api.middleware.exception_handlers import register_exception_handlers
from api.middleware.rate_limit import limiter
from api.routes import auth, calculate, health, invitations, opinions, projects, users
from tests.shared.helpers import (  # noqa: F401
    DEFAULT_TEST_PASSWORD,
    auth_header,
    mock_datetime_offset,
)


def create_test_app() -> FastAPI:
    """Create FastAPI app without lifespan for testing.

    Includes all API routers and exception handlers for integration testing.
    """
    settings = get_settings()
    app = FastAPI(
        title="BeCoMe API Test",
        version=settings.api_version,
    )

    # Rate limiting setup (required for auth routes)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # CSRF double-submit guard (dormant unless the request carries the csrf_token cookie).
    app.add_middleware(CSRFMiddleware)

    # Register exception handlers (OCP: centralized error handling)
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(calculate.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(projects.router)
    app.include_router(invitations.router)
    app.include_router(opinions.router)
    return app


def register_and_login(client: TestClient, email: str = "test@example.com") -> str:
    """Register a user and return their access token.

    :param client: Test client instance
    :param email: User email (default: test@example.com)
    :return: JWT access token
    """
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": DEFAULT_TEST_PASSWORD,
            "first_name": "Test",
            "last_name": "User",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": DEFAULT_TEST_PASSWORD},
    )
    # Drop the session cookies the login set, so header-based tests authenticate purely
    # via the returned token; otherwise an ambient cookie would override an explicit
    # Authorization header (e.g. a later login as another user).
    client.cookies.clear()
    return response.json()["access_token"]


def create_project(client: TestClient, token: str, name: str = "Test Project") -> dict:
    """Create a project and return its data.

    :param client: Test client instance
    :param token: Admin user's access token
    :param name: Project name
    :return: Project response data
    """
    response = client.post(
        "/api/v1/projects",
        json={"name": name},
        headers=auth_header(token),
    )
    return response.json()


def submit_opinion(
    client: TestClient,
    token: str,
    project_id: str,
    lower_bound: float = 40.0,
    peak: float = 60.0,
    upper_bound: float = 80.0,
    position: str = "Expert",
) -> dict:
    """Submit an opinion and return response data.

    :param client: Test client instance
    :param token: User's access token
    :param project_id: Project UUID string
    :param lower_bound: Fuzzy number lower bound
    :param peak: Fuzzy number peak
    :param upper_bound: Fuzzy number upper bound
    :param position: Expert's position
    :return: Opinion response data
    """
    response = client.post(
        f"/api/v1/projects/{project_id}/opinions",
        json={
            "position": position,
            "lower_bound": lower_bound,
            "peak": peak,
            "upper_bound": upper_bound,
        },
        headers=auth_header(token),
    )
    return response.json()


@pytest.fixture
def test_engine():
    """Create in-memory SQLite engine for testing.

    Uses yield to ensure proper cleanup with engine.dispose()
    to avoid ResourceWarning about unclosed database connections.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(test_engine):
    """Create a database session for testing."""
    with Session(test_engine) as session:
        yield session


@pytest.fixture(autouse=True)
def _reset_auth_throttles():
    """Give each test fresh login and reset-email throttles.

    Both ``get_login_throttle`` and ``get_reset_email_throttle`` are lru_cache
    singletons, so their in-memory state would otherwise leak between tests that
    reuse an email address.
    """
    from api.auth.login_throttle import get_login_throttle
    from api.auth.reset_throttle import get_reset_email_throttle

    get_login_throttle.cache_clear()
    get_reset_email_throttle.cache_clear()
    yield
    get_login_throttle.cache_clear()
    get_reset_email_throttle.cache_clear()


class _HeaderOnlyClient(TestClient):
    """Test client that discards response cookies after each request.

    Existing tests authenticate with an explicit Authorization header. Dropping the
    session cookies the app now sets keeps them isolated from cookie/CSRF behaviour: no
    ambient cookie overrides the header, and the CSRF check stays dormant. The cookie and
    CSRF flow is exercised through the plain ``cookie_client`` fixture instead.
    """

    def request(self, *args, **kwargs):
        response = super().request(*args, **kwargs)
        self.cookies.clear()
        return response


@pytest.fixture
def client(test_engine):
    """Create a header-auth test client (session cookies are not retained)."""
    test_app = create_test_app()

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    test_app.dependency_overrides[get_session] = override_get_session

    with _HeaderOnlyClient(test_app) as test_client:
        yield test_client


@pytest.fixture
def cookie_client(test_engine):
    """Create a cookie-retaining test client for the cookie + CSRF session flow."""
    test_app = create_test_app()

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    test_app.dependency_overrides[get_session] = override_get_session

    with TestClient(test_app) as test_client:
        yield test_client


@pytest.fixture
def client_with_session(test_engine):
    """Create test client with access to database session for direct manipulation.

    Useful for tests that need to modify database state directly.
    Uses the same session instance for both app and test code to avoid
    transaction isolation issues.
    """
    test_app = create_test_app()

    with Session(test_engine) as session:

        def override_get_session():
            yield session

        test_app.dependency_overrides[get_session] = override_get_session

        with _HeaderOnlyClient(test_app) as test_client:
            yield test_client, session
