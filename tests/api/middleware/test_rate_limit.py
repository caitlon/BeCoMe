"""Tests for rate limiting middleware."""

from unittest.mock import MagicMock, patch

from api.middleware.rate_limit import _get_client_ip


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
