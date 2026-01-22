"""Tests for authentication endpoints."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from api.config import get_settings
from api.db.models import (  # noqa: F401 - import all models to register in metadata
    CalculationResult,
    ExpertOpinion,
    Invitation,
    PasswordResetToken,
    Project,
    ProjectMember,
    User,
)
from api.db.session import get_session
from api.middleware.exception_handlers import register_exception_handlers
from api.routes import auth, calculate, health


def _create_test_app() -> FastAPI:
    """Create FastAPI app without lifespan for testing."""
    settings = get_settings()
    app = FastAPI(
        title="BeCoMe API Test",
        version=settings.api_version,
    )
    # Register exception handlers (OCP: centralized error handling)
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(calculate.router)
    app.include_router(auth.router)
    return app


@pytest.fixture
def client():
    """Create test client with in-memory database.

    Uses yield pattern with engine.dispose() for proper resource cleanup.
    """
    # Create engine with StaticPool to share in-memory DB across connections
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Create all tables in test engine
    SQLModel.metadata.create_all(test_engine)

    # Create test app without lifespan
    test_app = _create_test_app()

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    test_app.dependency_overrides[get_session] = override_get_session

    with TestClient(test_app) as test_client:
        yield test_client

    test_engine.dispose()


class TestRegister:
    """Tests for POST /api/v1/auth/register."""

    def test_register_creates_user(self, client):
        """Registration with valid data creates user and returns profile."""
        # GIVEN
        payload = {
            "email": "test@example.com",
            "password": "securepassword123",
            "first_name": "John",
            "last_name": "Doe",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert "id" in data
        assert "password" not in data
        assert "hashed_password" not in data

    def test_register_without_last_name(self, client):
        """Registration works without optional last_name."""
        # GIVEN
        payload = {
            "email": "jane@example.com",
            "password": "securepassword123",
            "first_name": "Jane",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 201
        data = response.json()
        assert data["last_name"] is None

    def test_register_duplicate_email_fails(self, client):
        """Registration with existing email returns 409."""
        # GIVEN - first registration
        payload = {
            "email": "duplicate@example.com",
            "password": "securepassword123",
            "first_name": "First",
        }
        client.post("/api/v1/auth/register", json=payload)

        # WHEN - second registration with same email
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    def test_register_duplicate_email_different_case_fails(self, client):
        """Registration with same email in different case returns 409."""
        # GIVEN - first registration with mixed case email
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "Test@Example.COM",
                "password": "securepassword123",
                "first_name": "First",
            },
        )

        # WHEN - second registration with lowercase email
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "securepassword123",
                "first_name": "Second",
            },
        )

        # THEN
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    def test_login_with_different_case_email_works(self, client):
        """Login works with email in different case than registered."""
        # GIVEN - register with mixed case
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "CaseTest@Example.COM",
                "password": "securepassword123",
                "first_name": "Case",
            },
        )

        # WHEN - login with lowercase
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "casetest@example.com", "password": "securepassword123"},
        )

        # THEN
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_register_short_password_fails(self, client):
        """Registration with password < 8 chars returns 422."""
        # GIVEN
        payload = {
            "email": "short@example.com",
            "password": "short",
            "first_name": "Short",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422

    def test_register_invalid_email_fails(self, client):
        """Registration with invalid email returns 422."""
        # GIVEN
        payload = {
            "email": "not-an-email",
            "password": "securepassword123",
            "first_name": "Bad",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    def test_login_returns_token(self, client):
        """Login with valid credentials returns JWT token."""
        # GIVEN - register user first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@example.com",
                "password": "securepassword123",
                "first_name": "Login",
            },
        )

        # WHEN - login with OAuth2 form data
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "login@example.com", "password": "securepassword123"},
        )

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password_fails(self, client):
        """Login with incorrect password returns 401."""
        # GIVEN
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpass@example.com",
                "password": "correctpassword",
                "first_name": "Wrong",
            },
        )

        # WHEN
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "wrongpass@example.com", "password": "incorrectpassword"},
        )

        # THEN
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    def test_login_nonexistent_user_fails(self, client):
        """Login with non-existent email returns 401."""
        # WHEN
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "nobody@example.com", "password": "anypassword"},
        )

        # THEN
        assert response.status_code == 401


class TestMe:
    """Tests for GET /api/v1/auth/me."""

    def test_me_returns_profile(self, client):
        """Authenticated request returns user profile."""
        # GIVEN - register and login
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "me@example.com",
                "password": "securepassword123",
                "first_name": "Me",
                "last_name": "User",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": "me@example.com", "password": "securepassword123"},
        )
        token = login_response.json()["access_token"]

        # WHEN
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@example.com"
        assert data["first_name"] == "Me"
        assert data["last_name"] == "User"

    def test_me_without_token_fails(self, client):
        """Request without token returns 401."""
        # WHEN
        response = client.get("/api/v1/auth/me")

        # THEN
        assert response.status_code == 401

    def test_me_with_invalid_token_fails(self, client):
        """Request with invalid token returns 401."""
        # WHEN
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        # THEN
        assert response.status_code == 401

    def test_me_with_deleted_user_fails(self, client):
        """Request with valid token but deleted user returns 401."""
        # GIVEN - register, login, then delete user
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "deleted@example.com",
                "password": "securepassword123",
                "first_name": "Deleted",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": "deleted@example.com", "password": "securepassword123"},
        )
        token = login_response.json()["access_token"]

        # Delete user directly from database
        from api.db.session import get_session

        session = next(client.app.dependency_overrides[get_session]())
        user = session.exec(
            __import__("sqlmodel").select(User).where(User.email == "deleted@example.com")
        ).first()
        session.delete(user)
        session.commit()

        # WHEN - try to use token for deleted user
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        # THEN
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]
