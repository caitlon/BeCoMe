"""Tests for the shared client-IP extraction helper."""

from unittest.mock import MagicMock

from api.utils.client_ip import get_client_ip


class TestGetClientIp:
    """get_client_ip resolves the caller IP across proxy and direct setups."""

    def test_returns_forwarded_ip_when_present(self):
        """GIVEN an X-Forwarded-For header WHEN extracting THEN the header wins."""
        # GIVEN
        request = MagicMock()
        request.headers.get.return_value = "203.0.113.50"

        # WHEN
        result = get_client_ip(request)

        # THEN
        assert result == "203.0.113.50"
        request.headers.get.assert_called_once_with("X-Forwarded-For")

    def test_returns_first_ip_from_comma_list(self):
        """GIVEN a multi-hop forwarded header WHEN extracting THEN the first IP wins."""
        # GIVEN
        request = MagicMock()
        request.headers.get.return_value = "203.0.113.50, 70.41.3.18, 150.172.238.178"

        # WHEN / THEN
        assert get_client_ip(request) == "203.0.113.50"

    def test_strips_whitespace_from_forwarded_ip(self):
        """GIVEN whitespace around the forwarded IP WHEN extracting THEN it is trimmed."""
        # GIVEN
        request = MagicMock()
        request.headers.get.return_value = "  192.168.1.1  , 10.0.0.1"

        # WHEN / THEN
        assert get_client_ip(request) == "192.168.1.1"

    def test_falls_back_to_client_host(self):
        """GIVEN no forwarded header WHEN extracting THEN the direct peer host is used."""
        # GIVEN
        request = MagicMock()
        request.headers.get.return_value = None
        request.client.host = "127.0.0.1"

        # WHEN / THEN
        assert get_client_ip(request) == "127.0.0.1"

    def test_returns_unknown_when_no_client(self):
        """GIVEN no header and no client WHEN extracting THEN it is 'unknown'."""
        # GIVEN
        request = MagicMock()
        request.headers.get.return_value = None
        request.client = None

        # WHEN / THEN
        assert get_client_ip(request) == "unknown"

    def test_returns_unknown_for_none_request(self):
        """GIVEN no request WHEN extracting THEN it is 'unknown'."""
        # WHEN / THEN
        assert get_client_ip(None) == "unknown"
