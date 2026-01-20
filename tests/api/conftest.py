"""Pytest fixtures for API tests."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for API testing."""
    return TestClient(app)


@pytest.fixture
def test_engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(test_engine):
    """Create a database session for testing."""
    with Session(test_engine) as session:
        yield session
