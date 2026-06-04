"""Integration tests that the application factory wires request logging."""

from fastapi.testclient import TestClient

from api.main import create_app


class TestRequestLoggingWiring:
    """Tests that the application factory wires request logging."""

    def test_app_returns_request_id_header(self):
        """
        GIVEN the full application
        WHEN any endpoint is called
        THEN the response carries an X-Request-ID header
        """
        # GIVEN
        live_client = TestClient(create_app())

        # WHEN
        response = live_client.get("/api/v1/health")

        # THEN
        assert response.headers.get("X-Request-ID")

    def test_cors_allows_request_id_header(self):
        """
        GIVEN the full application
        WHEN a CORS preflight asks to send X-Request-ID
        THEN the header is allowed
        """
        # GIVEN
        live_client = TestClient(create_app())

        # WHEN
        response = live_client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Request-ID",
            },
        )

        # THEN
        allowed = response.headers.get("Access-Control-Allow-Headers", "")
        assert "x-request-id" in allowed.lower()
