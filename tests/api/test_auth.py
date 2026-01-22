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
from api.routes import auth, calculate, health, users


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
    app.include_router(users.router)
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
            "password": "SecurePass123",
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

    def test_register_without_last_name_fails(self, client):
        """Registration without last_name returns 422."""
        # GIVEN
        payload = {
            "email": "jane@example.com",
            "password": "SecurePass123",
            "first_name": "Jane",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422

    def test_register_duplicate_email_fails(self, client):
        """Registration with existing email returns 409."""
        # GIVEN - first registration
        payload = {
            "email": "duplicate@example.com",
            "password": "SecurePass123",
            "first_name": "First",
            "last_name": "User",
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
                "password": "SecurePass123",
                "first_name": "First",
                "last_name": "User",
            },
        )

        # WHEN - second registration with lowercase email
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "SecurePass123",
                "first_name": "Second",
                "last_name": "User",
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
                "password": "SecurePass123",
                "first_name": "Case",
                "last_name": "Test",
            },
        )

        # WHEN - login with lowercase
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "casetest@example.com", "password": "SecurePass123"},
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
            "last_name": "Pass",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422

    def test_register_password_without_uppercase_fails(self, client):
        """Registration with password missing uppercase letter returns 422."""
        # GIVEN
        payload = {
            "email": "nouppercase@example.com",
            "password": "password123",
            "first_name": "Test",
            "last_name": "User",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422
        assert "uppercase" in response.json()["detail"][0]["msg"].lower()

    def test_register_password_without_lowercase_fails(self, client):
        """Registration with password missing lowercase letter returns 422."""
        # GIVEN
        payload = {
            "email": "nolowercase@example.com",
            "password": "PASSWORD123",
            "first_name": "Test",
            "last_name": "User",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422
        assert "lowercase" in response.json()["detail"][0]["msg"].lower()

    def test_register_password_without_digit_fails(self, client):
        """Registration with password missing digit returns 422."""
        # GIVEN
        payload = {
            "email": "nodigit@example.com",
            "password": "PasswordABC",
            "first_name": "Test",
            "last_name": "User",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422
        assert "digit" in response.json()["detail"][0]["msg"].lower()

    def test_register_invalid_email_fails(self, client):
        """Registration with invalid email returns 422."""
        # GIVEN
        payload = {
            "email": "not-an-email",
            "password": "SecurePass123",
            "first_name": "Bad",
            "last_name": "Email",
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
                "password": "SecurePass123",
                "first_name": "Login",
                "last_name": "User",
            },
        )

        # WHEN - login with OAuth2 form data
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "login@example.com", "password": "SecurePass123"},
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
                "password": "CorrectPass1",
                "first_name": "Wrong",
                "last_name": "Pass",
            },
        )

        # WHEN
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "wrongpass@example.com", "password": "WrongPass999"},
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
                "password": "SecurePass123",
                "first_name": "Me",
                "last_name": "User",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": "me@example.com", "password": "SecurePass123"},
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
                "password": "SecurePass123",
                "first_name": "Deleted",
                "last_name": "User",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": "deleted@example.com", "password": "SecurePass123"},
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


class TestEmailValidation:
    """Tests for email ASCII validation."""

    def test_register_email_with_cyrillic_fails(self, client):
        """Registration with Cyrillic email returns 422."""
        # GIVEN
        payload = {
            "email": "тест@example.com",
            "password": "SecurePass123",
            "first_name": "Test",
            "last_name": "User",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422
        assert "ascii" in response.json()["detail"][0]["msg"].lower()

    def test_register_email_ascii_succeeds(self, client):
        """Registration with ASCII email succeeds."""
        # GIVEN
        payload = {
            "email": "test.user+tag@example.com",
            "password": "SecurePass123",
            "first_name": "Test",
            "last_name": "User",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 201
        assert response.json()["email"] == "test.user+tag@example.com"


class TestNameValidation:
    """Tests for first_name and last_name validation."""

    def test_register_name_with_digits_fails(self, client):
        """Registration with digits in name returns 422."""
        # GIVEN
        payload = {
            "email": "digits@example.com",
            "password": "SecurePass123",
            "first_name": "John123",
            "last_name": "Doe",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422
        assert "letters" in response.json()["detail"][0]["msg"].lower()

    def test_register_name_with_special_chars_fails(self, client):
        """Registration with special characters in name returns 422."""
        # GIVEN
        payload = {
            "email": "special@example.com",
            "password": "SecurePass123",
            "first_name": "John@#$",
            "last_name": "Doe",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422

    def test_register_name_with_hyphen_succeeds(self, client):
        """Registration with hyphenated name succeeds."""
        # GIVEN
        payload = {
            "email": "hyphen@example.com",
            "password": "SecurePass123",
            "first_name": "Jean-Pierre",
            "last_name": "Dupont",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 201
        assert response.json()["first_name"] == "Jean-Pierre"

    def test_register_name_with_apostrophe_succeeds(self, client):
        """Registration with apostrophe in name succeeds."""
        # GIVEN
        payload = {
            "email": "apostrophe@example.com",
            "password": "SecurePass123",
            "first_name": "O'Brien",
            "last_name": "Smith",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 201
        assert response.json()["first_name"] == "O'Brien"

    def test_register_cyrillic_name_succeeds(self, client):
        """Registration with Cyrillic name succeeds."""
        # GIVEN
        payload = {
            "email": "cyrillic@example.com",
            "password": "SecurePass123",
            "first_name": "Олег",
            "last_name": "Петров",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 201
        assert response.json()["first_name"] == "Олег"
        assert response.json()["last_name"] == "Петров"

    def test_register_name_with_space_succeeds(self, client):
        """Registration with space in name succeeds."""
        # GIVEN
        payload = {
            "email": "space@example.com",
            "password": "SecurePass123",
            "first_name": "Anna Maria",
            "last_name": "Kowalski",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 201
        assert response.json()["first_name"] == "Anna Maria"

    def test_register_last_name_with_digits_fails(self, client):
        """Registration with digits in last name returns 422."""
        # GIVEN
        payload = {
            "email": "lastdigits@example.com",
            "password": "SecurePass123",
            "first_name": "John",
            "last_name": "Doe123",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422

    def test_register_empty_last_name_fails(self, client):
        """Registration with empty last name returns 422."""
        # GIVEN
        payload = {
            "email": "emptylast@example.com",
            "password": "SecurePass123",
            "first_name": "John",
            "last_name": "",
        }

        # WHEN
        response = client.post("/api/v1/auth/register", json=payload)

        # THEN
        assert response.status_code == 422


class TestProfileUpdate:
    """Tests for PUT /api/v1/users/me profile update validation."""

    def _get_auth_header(self, client) -> dict:
        """Register and login, return auth header."""
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "profile@example.com",
                "password": "SecurePass123",
                "first_name": "Profile",
                "last_name": "User",
            },
        )
        login = client.post(
            "/api/v1/auth/login",
            data={"username": "profile@example.com", "password": "SecurePass123"},
        )
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_update_profile_name_with_digits_fails(self, client):
        """Profile update with digits in name returns 422."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me",
            json={"first_name": "John123"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 422
        assert "letters" in response.json()["detail"][0]["msg"].lower()

    def test_update_profile_valid_name_succeeds(self, client):
        """Profile update with valid name succeeds."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me",
            json={"first_name": "Jean-Pierre", "last_name": "O'Connor"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 200
        assert response.json()["first_name"] == "Jean-Pierre"
        assert response.json()["last_name"] == "O'Connor"

    def test_update_profile_cyrillic_name_succeeds(self, client):
        """Profile update with Cyrillic name succeeds."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me",
            json={"first_name": "Алексей"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 200
        assert response.json()["first_name"] == "Алексей"

    def test_update_profile_empty_last_name_is_ignored(self, client):
        """Profile update with empty last name doesn't change it."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me",
            json={"last_name": ""},
            headers=headers,
        )

        # THEN - empty string converted to None means "no update"
        assert response.status_code == 200
        assert response.json()["last_name"] == "User"  # unchanged

    def test_update_profile_empty_first_name_is_ignored(self, client):
        """Profile update with empty first name doesn't change it."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me",
            json={"first_name": ""},
            headers=headers,
        )

        # THEN - empty string converted to None means "no update"
        assert response.status_code == 200
        assert response.json()["first_name"] == "Profile"  # unchanged


class TestPasswordChange:
    """Tests for PUT /api/v1/users/me/password validation."""

    def _get_auth_header(self, client) -> dict:
        """Register and login, return auth header."""
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "pwchange@example.com",
                "password": "OldPass123",
                "first_name": "Password",
                "last_name": "Change",
            },
        )
        login = client.post(
            "/api/v1/auth/login",
            data={"username": "pwchange@example.com", "password": "OldPass123"},
        )
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_change_password_without_uppercase_fails(self, client):
        """Password change without uppercase letter returns 422."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me/password",
            json={"current_password": "OldPass123", "new_password": "newpass123"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 422
        assert "uppercase" in response.json()["detail"][0]["msg"].lower()

    def test_change_password_without_lowercase_fails(self, client):
        """Password change without lowercase letter returns 422."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me/password",
            json={"current_password": "OldPass123", "new_password": "NEWPASS123"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 422
        assert "lowercase" in response.json()["detail"][0]["msg"].lower()

    def test_change_password_without_digit_fails(self, client):
        """Password change without digit returns 422."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me/password",
            json={"current_password": "OldPass123", "new_password": "NewPassABC"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 422
        assert "digit" in response.json()["detail"][0]["msg"].lower()

    def test_change_password_valid_succeeds(self, client):
        """Password change with valid password succeeds."""
        # GIVEN
        headers = self._get_auth_header(client)

        # WHEN
        response = client.put(
            "/api/v1/users/me/password",
            json={"current_password": "OldPass123", "new_password": "NewPass456"},
            headers=headers,
        )

        # THEN
        assert response.status_code == 204
