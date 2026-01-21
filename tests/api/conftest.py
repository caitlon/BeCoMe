"""Pytest fixtures and helpers for API tests."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
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
from api.dependencies import get_session
from api.routes import auth, calculate, health, invitations, projects


def create_test_app() -> FastAPI:
    """Create FastAPI app without lifespan for testing.

    Includes all API routers for integration testing.
    """
    settings = get_settings()
    app = FastAPI(
        title="BeCoMe API Test",
        version=settings.api_version,
    )
    app.include_router(health.router)
    app.include_router(calculate.router)
    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(invitations.router)
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
            "password": "password123",
            "first_name": "Test",
            "last_name": "User",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "password123"},
    )
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    """Create authorization header from token.

    :param token: JWT access token
    :return: Headers dict with Bearer authorization
    """
    return {"Authorization": f"Bearer {token}"}


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


@pytest.fixture
def test_engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(test_engine):
    """Create a database session for testing."""
    with Session(test_engine) as session:
        yield session


@pytest.fixture
def client(test_engine):
    """Create test client with in-memory database."""
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

        with TestClient(test_app) as test_client:
            yield test_client, session
