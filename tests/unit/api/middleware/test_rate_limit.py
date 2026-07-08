"""Tests for rate limiting middleware."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from api.middleware.rate_limit import build_limiter, rate_limit_handler


class TestRateLimitHandler:
    """Tests for the logging rate-limit handler wrapper."""

    def test_logs_violation_as_warning(self):
        """
        GIVEN a rate-limit violation
        WHEN rate_limit_handler runs
        THEN it logs a WARNING carrying the path and client IP
        """
        # GIVEN
        request = MagicMock()
        request.url.path = "/auth/login"
        request.state.request_id = "rid-9"
        exc = MagicMock()

        # WHEN
        with (
            patch("api.middleware.rate_limit.logger") as mock_logger,
            patch("api.middleware.rate_limit._rate_limit_exceeded_handler"),
            patch("api.middleware.rate_limit.get_client_ip", return_value="203.0.113.7"),
        ):
            rate_limit_handler(request, exc)

        # THEN
        mock_logger.warning.assert_called_once()
        extra = mock_logger.warning.call_args[1]["extra"]
        assert extra["path"] == "/auth/login"
        assert extra["ip"] == "203.0.113.7"

    def test_delegates_to_slowapi_handler(self):
        """
        GIVEN a rate-limit violation
        WHEN rate_limit_handler runs
        THEN it returns the response from the slowapi handler
        """
        # GIVEN
        request = MagicMock()
        exc = MagicMock()
        sentinel = MagicMock()

        # WHEN
        with (
            patch("api.middleware.rate_limit.logger"),
            patch(
                "api.middleware.rate_limit._rate_limit_exceeded_handler",
                return_value=sentinel,
            ) as mock_delegate,
        ):
            result = rate_limit_handler(request, exc)

        # THEN
        assert result is sentinel
        mock_delegate.assert_called_once_with(request, exc)


class TestRateLimitWiring:
    """Tests that the app factory wires the logging rate-limit handler."""

    def test_app_registers_logging_rate_limit_handler(self):
        """
        GIVEN the full application
        WHEN it is created
        THEN RateLimitExceeded is handled by rate_limit_handler
        """
        # GIVEN
        from slowapi.errors import RateLimitExceeded

        from api.main import create_app

        # WHEN
        app = create_app()

        # THEN
        assert app.exception_handlers[RateLimitExceeded] is rate_limit_handler

    def test_app_registers_slowapi_middleware(self):
        """
        GIVEN the full application
        WHEN it is created
        THEN SlowAPIMiddleware is installed so default_limits apply to every route
        """
        # GIVEN
        from slowapi.middleware import SlowAPIMiddleware

        from api.main import create_app

        # WHEN
        app = create_app()

        # THEN
        assert any(middleware.cls is SlowAPIMiddleware for middleware in app.user_middleware)


class TestBuildLimiter:
    """Tests that build_limiter wires the storage backend and fail-open flag."""

    def test_uses_redis_storage_when_configured(self):
        """
        GIVEN settings with a redis_url
        WHEN build_limiter runs
        THEN the limiter uses that storage URI and swallows storage errors (fail-open)
        """
        settings = SimpleNamespace(testing=False, redis_url="redis://localhost:6379/0")
        limiter = build_limiter(settings)
        assert limiter._storage_uri == "redis://localhost:6379/0"
        assert limiter._swallow_errors is True

    def test_no_storage_uri_without_redis(self):
        """
        GIVEN settings without a redis_url
        WHEN build_limiter runs
        THEN no storage URI is set (slowapi defaults to in-memory) and it still fails open
        """
        settings = SimpleNamespace(testing=True, redis_url="")
        limiter = build_limiter(settings)
        assert limiter._storage_uri is None
        assert limiter._swallow_errors is True

    def test_applies_a_global_default_limit(self):
        """
        GIVEN any settings
        WHEN build_limiter runs
        THEN a non-empty default limit is configured so no route is left unthrottled
        """
        settings = SimpleNamespace(testing=False, redis_url="redis://localhost:6379/0")
        limiter = build_limiter(settings)
        assert limiter._default_limits

    def test_enables_in_memory_fallback(self):
        """
        GIVEN settings with a redis_url
        WHEN build_limiter runs
        THEN in-memory fallback is enabled so a Redis outage still enforces a limit
        rather than letting every request through unthrottled
        """
        settings = SimpleNamespace(testing=False, redis_url="redis://localhost:6379/0")
        limiter = build_limiter(settings)
        assert limiter._in_memory_fallback_enabled is True
