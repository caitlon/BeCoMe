"""Tests for the CSRF exempt-path policy."""

from api.middleware.csrf import _csrf_exempt


class TestCsrfExempt:
    """Pre-session auth endpoints are exempt from CSRF; logout and app routes are not."""

    def test_login_is_exempt(self):
        assert _csrf_exempt("/api/v1/auth/login") is True

    def test_refresh_is_exempt(self):
        assert _csrf_exempt("/api/v1/auth/refresh") is True

    def test_logout_is_not_exempt(self):
        assert _csrf_exempt("/api/v1/auth/logout") is False

    def test_app_route_is_not_exempt(self):
        assert _csrf_exempt("/api/v1/projects") is False
