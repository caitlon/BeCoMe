"""Tests for security headers middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.security_headers import SecurityHeadersMiddleware


@pytest.fixture
def app_with_middleware() -> FastAPI:
    """Create a minimal FastAPI app with SecurityHeadersMiddleware."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"status": "ok"}

    return app


@pytest.fixture
def http_client(app_with_middleware: FastAPI) -> TestClient:
    """Create HTTP TestClient for the app."""
    return TestClient(app_with_middleware)


@pytest.fixture
def https_client(app_with_middleware: FastAPI) -> TestClient:
    """Create HTTPS TestClient for the app."""
    return TestClient(app_with_middleware, base_url="https://testserver")


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware."""

    def test_adds_x_frame_options(self, http_client: TestClient):
        """
        GIVEN a request to any endpoint
        WHEN the response is returned
        THEN it includes X-Frame-Options: DENY
        """
        # WHEN
        response = http_client.get("/test")

        # THEN
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_adds_x_content_type_options(self, http_client: TestClient):
        """
        GIVEN a request to any endpoint
        WHEN the response is returned
        THEN it includes X-Content-Type-Options: nosniff
        """
        # WHEN
        response = http_client.get("/test")

        # THEN
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_adds_x_xss_protection(self, http_client: TestClient):
        """
        GIVEN a request to any endpoint
        WHEN the response is returned
        THEN it includes X-XSS-Protection: 1; mode=block
        """
        # WHEN
        response = http_client.get("/test")

        # THEN
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_skips_hsts_for_http(self, http_client: TestClient):
        """
        GIVEN an HTTP request (not HTTPS)
        WHEN the response is returned
        THEN it does NOT include Strict-Transport-Security header
        """
        # WHEN
        response = http_client.get("/test")

        # THEN - HSTS should not be present for HTTP
        assert "Strict-Transport-Security" not in response.headers

    def test_adds_hsts_for_https(self, https_client: TestClient):
        """
        GIVEN an HTTPS request
        WHEN the response is returned
        THEN it includes Strict-Transport-Security header
        """
        # WHEN
        response = https_client.get("/test")

        # THEN
        hsts = response.headers.get("Strict-Transport-Security")
        assert hsts == "max-age=31536000; includeSubDomains; preload"

    def test_adds_referrer_policy(self, http_client: TestClient):
        """
        GIVEN a request to any endpoint
        WHEN the response is returned
        THEN it includes Referrer-Policy: strict-origin-when-cross-origin
        """
        # WHEN
        response = http_client.get("/test")

        # THEN
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_adds_permissions_policy(self, http_client: TestClient):
        """
        GIVEN a request to any endpoint
        WHEN the response is returned
        THEN it includes Permissions-Policy disabling browser features
        """
        # WHEN
        response = http_client.get("/test")

        # THEN
        policy = response.headers.get("Permissions-Policy")
        assert policy is not None
        assert "camera=()" in policy
        assert "microphone=()" in policy
        assert "geolocation=()" in policy

    def test_adds_content_security_policy(self, http_client: TestClient):
        """
        GIVEN a request to any endpoint
        WHEN the response is returned
        THEN it includes Content-Security-Policy header
        """
        # WHEN
        response = http_client.get("/test")

        # THEN
        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "script-src 'self'" in csp
