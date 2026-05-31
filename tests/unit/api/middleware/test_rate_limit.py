"""Tests for rate limiting middleware."""

from unittest.mock import MagicMock, patch

from api.middleware.rate_limit import _get_client_ip, rate_limit_handler


class TestGetClientIp:
    """Tests for _get_client_ip function."""

    def test_returns_forwarded_ip_when_present(self):
        """
        GIVEN a request with X-Forwarded-For header
        WHEN _get_client_ip is called
        THEN it returns the forwarded IP address
        """
        # GIVEN
        request = MagicMock()
        request.headers.get.return_value = "203.0.113.50"

        # WHEN
        result = _get_client_ip(request)

        # THEN
        assert result == "203.0.113.50"
        request.headers.get.assert_called_once_with("X-Forwarded-For")

    def test_returns_first_ip_from_comma_list(self):
        """
        GIVEN a request with multiple IPs in X-Forwarded-For
        WHEN _get_client_ip is called
        THEN it returns the first IP (original client)
        """
        # GIVEN
        request = MagicMock()
        request.headers.get.return_value = "203.0.113.50,198.51.100.1,192.0.2.1"

        # WHEN
        result = _get_client_ip(request)

        # THEN
        assert result == "203.0.113.50"

    def test_strips_whitespace_from_forwarded_ip(self):
        """
        GIVEN a request with whitespace around IP in X-Forwarded-For
        WHEN _get_client_ip is called
        THEN it strips the whitespace
        """
        # GIVEN
        request = MagicMock()
        request.headers.get.return_value = "  203.0.113.50  , 198.51.100.1"

        # WHEN
        result = _get_client_ip(request)

        # THEN
        assert result == "203.0.113.50"

    def test_falls_back_to_remote_address_when_no_header(self):
        """
        GIVEN a request without X-Forwarded-For header
        WHEN _get_client_ip is called
        THEN it falls back to get_remote_address
        """
        # GIVEN
        request = MagicMock()
        request.headers.get.return_value = None

        with patch(
            "api.middleware.rate_limit.get_remote_address",
            return_value="127.0.0.1",
        ) as mock_get_remote:
            # WHEN
            result = _get_client_ip(request)

            # THEN
            assert result == "127.0.0.1"
            mock_get_remote.assert_called_once_with(request)


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
