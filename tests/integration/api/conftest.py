"""Pytest fixtures and helpers for API integration tests."""

import os
from contextlib import contextmanager

# Select the test profile before importing api modules (settings are cached on first use)
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ["TESTING"] = "1"  # Must always be set; rate limiter reads it at import time

import dns.asyncresolver
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from api.config import get_settings
from api.db.models import (  # noqa: F401 - models required for SQLModel.metadata.create_all
    CalculationResult,
    EmailVerificationToken,
    ExpertOpinion,
    Invitation,
    PasswordResetToken,
    Project,
    ProjectMember,
    User,
)
from api.db.session import get_session
from api.db.utils import utc_now
from api.dependencies import get_email_address_policy
from api.middleware.csrf import CSRFMiddleware
from api.middleware.exception_handlers import register_exception_handlers
from api.middleware.rate_limit import limiter
from api.routes import auth, calculate, health, invitations, opinions, projects, users
from api.services.email_policy import EmailAddressPolicy
from api.services.user_cache import get_user_cache
from tests.shared.helpers import (  # noqa: F401
    DEFAULT_TEST_PASSWORD,
    auth_header,
    mock_datetime_offset,
)

# Registration address policy for the integration app, with the DNS half switched off so
# no test ever depends on a live resolver. The blocklist half stays on: it is a local
# lookup and the registration tests assert on it. The MX half is covered against a
# stubbed resolver in tests/unit/api/services/test_email_policy.py, and the tests that
# need a route-level DNS rejection override this dependency again with their own stub.
# The resolver is built with configure=False so importing this module never reads
# /etc/resolv.conf (which is absent in some containers).
_OFFLINE_EMAIL_POLICY = EmailAddressPolicy(
    resolver=dns.asyncresolver.Resolver(configure=False),
    mx_check_enabled=False,
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

    app.dependency_overrides[get_email_address_policy] = lambda: _OFFLINE_EMAIL_POLICY

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


@contextmanager
def app_session(client: TestClient):
    """Yield a database session bound to the engine the test app writes through.

    Lets a test set up or inspect state the API exposes no endpoint for, using the
    same connection the app uses so nothing is hidden behind an open transaction.

    :param client: Test client whose app has get_session overridden.
    """
    generator = client.app.dependency_overrides[get_session]()
    try:
        yield next(generator)
    finally:
        generator.close()


def register(
    client: TestClient,
    email: str,
    password: str = DEFAULT_TEST_PASSWORD,
    first_name: str = "Test",
    last_name: str = "User",
):
    """Post a registration and return the raw response.

    :param client: Test client instance
    :param email: Email to register
    :param password: Password to register with
    :param first_name: First name to register with
    :param last_name: Last name to register with
    :return: The registration response
    """
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
        },
    )


def mark_email_verified(client: TestClient, email: str) -> None:
    """Mark a registered address verified straight through the database.

    Registration only creates an unverified account, and login refuses those, so
    almost every test in the suite needs its fixture user activated. Doing it through
    the real register-mail-verify round trip would make every unrelated test depend on
    the verification feature (and on a captured email); writing the column directly is
    fast, deterministic, and keeps that coupling in one place. The real round trip is
    exercised in tests/integration/api/auth/test_email_verification.py.

    :param client: Test client instance
    :param email: Address of an already-registered account
    """
    with app_session(client) as session:
        user = session.exec(select(User).where(User.email == email.lower())).first()
        assert user is not None, f"no account is registered for {email}"
        user.email_verified_at = utc_now()
        session.add(user)
        session.commit()
        user_id = user.id
    get_user_cache().invalidate(user_id)


def stored_accounts(client: TestClient, email: str) -> list[dict]:
    """Return every stored account for an address, as plain field values.

    Registration no longer echoes the created user back, so tests that used to assert
    on the response body assert on the row instead. Values are copied out while the
    session is open, so callers never touch a detached ORM instance.

    :param client: Test client instance
    :param email: Address to look up (case-insensitive)
    :return: One dict per matching account (at most one -- the column is unique)
    """
    with app_session(client) as session:
        users = session.exec(select(User).where(User.email == email.lower())).all()
        return [
            {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email_verified_at": user.email_verified_at,
            }
            for user in users
        ]


def register_verified(
    client: TestClient,
    email: str,
    password: str = DEFAULT_TEST_PASSWORD,
    first_name: str = "Test",
    last_name: str = "User",
) -> None:
    """Register a user and activate the account, ready to log in.

    :param client: Test client instance
    :param email: Email to register
    :param password: Password to register with
    :param first_name: First name to register with
    :param last_name: Last name to register with
    """
    register(client, email, password, first_name, last_name)
    mark_email_verified(client, email)


def register_and_login(client: TestClient, email: str = "test@example.com") -> str:
    """Register a user, activate the account, and return their access token.

    :param client: Test client instance
    :param email: User email (default: test@example.com)
    :return: JWT access token
    """
    register_verified(client, email)
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
    """Give each test fresh login, activation, reset-email, and verification-email throttles.

    All four factories are lru_cache singletons, so their in-memory state would
    otherwise leak between tests that reuse an email address -- and every test that
    registers a user now goes through the verification-email throttle.
    """
    from api.auth.email_throttle import (
        get_reset_email_throttle,
        get_verification_email_throttle,
    )
    from api.auth.login_throttle import get_activation_throttle, get_login_throttle

    def clear_all():
        get_login_throttle.cache_clear()
        get_activation_throttle.cache_clear()
        get_reset_email_throttle.cache_clear()
        get_verification_email_throttle.cache_clear()

    clear_all()
    yield
    clear_all()


@pytest.fixture(autouse=True)
def _reset_user_cache():
    """Give each test a fresh user cache.

    ``get_user_cache`` is an lru_cache singleton whose in-memory state would
    otherwise leak between tests reusing a user id.
    """
    from api.services.user_cache import InMemoryUserCache

    get_user_cache.cache_clear()
    store = get_user_cache()
    if isinstance(store, InMemoryUserCache):
        store.clear()
    yield
    get_user_cache.cache_clear()


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
