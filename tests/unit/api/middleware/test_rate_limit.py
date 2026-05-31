"""Tests for rate limiting middleware."""

from unittest.mock import MagicMock, patch

from api.middleware.rate_limit import rate_limit_handler


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
        request.headers.get.return_value = "203.0.113.7"
        exc = MagicMock()

        # WHEN
        with (
            patch("api.middleware.rate_limit.logger") as mock_logger,
            patch("api.middleware.rate_limit._rate_limit_exceeded_handler"),
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
