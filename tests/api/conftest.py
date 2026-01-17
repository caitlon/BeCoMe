"""Pytest fixtures for API tests."""

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for API testing."""
    return TestClient(app)
