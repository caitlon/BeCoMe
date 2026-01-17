"""API tests for /health endpoint."""

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_returns_ok_status(self, client: TestClient):
        """
        GIVEN a running API
        WHEN GET /api/v1/health is called
        THEN response contains status 'ok'
        """
        # WHEN
        response = client.get("/api/v1/health")

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_version(self, client: TestClient):
        """
        GIVEN a running API
        WHEN GET /api/v1/health is called
        THEN response contains API version
        """
        # WHEN
        response = client.get("/api/v1/health")

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)
