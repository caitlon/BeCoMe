"""Tests for the shared client-IP extraction helper."""

from unittest.mock import MagicMock

from api.utils.client_ip import get_client_ip


def _request(
    headers: dict[str, str] | None = None,
    client_host: str | None = None,
) -> MagicMock:
    """Build a request mock whose header lookup is keyed by name.

    :param headers: Header name -> value map the mock should expose.
    :param client_host: Direct peer host, or ``None`` for no client.
    :return: Configured request mock.
    """
    request = MagicMock()
    request.headers.get.side_effect = lambda name, default=None: (headers or {}).get(name, default)
    if client_host is None:
        request.client = None
    else:
        request.client.host = client_host
    return request


class TestGetClientIp:
    """get_client_ip resolves the caller IP across proxy and direct setups."""

    def test_prefers_cf_connecting_ip_over_forwarded(self):
        """GIVEN both CF and forwarded headers WHEN extracting THEN Cloudflare wins."""
        # GIVEN -- X-Forwarded-For is client-spoofable, CF-Connecting-IP is not
        request = _request({"CF-Connecting-IP": "203.0.113.50", "X-Forwarded-For": "1.2.3.4"})

        # WHEN / THEN
        assert get_client_ip(request) == "203.0.113.50"

    def test_strips_whitespace_from_cf_connecting_ip(self):
        """GIVEN whitespace around the CF IP WHEN extracting THEN it is trimmed."""
        # GIVEN
        request = _request({"CF-Connecting-IP": "  203.0.113.50  "})

        # WHEN / THEN
        assert get_client_ip(request) == "203.0.113.50"

    def test_returns_forwarded_ip_when_no_cf_header(self):
        """GIVEN only an X-Forwarded-For header WHEN extracting THEN the header wins."""
        # GIVEN
        request = _request({"X-Forwarded-For": "203.0.113.50"})

        # WHEN / THEN
        assert get_client_ip(request) == "203.0.113.50"

    def test_returns_first_ip_from_comma_list(self):
        """GIVEN a multi-hop forwarded header WHEN extracting THEN the first IP wins."""
        # GIVEN
        request = _request({"X-Forwarded-For": "203.0.113.50, 70.41.3.18, 150.172.238.178"})

        # WHEN / THEN
        assert get_client_ip(request) == "203.0.113.50"

    def test_strips_whitespace_from_forwarded_ip(self):
        """GIVEN whitespace around the forwarded IP WHEN extracting THEN it is trimmed."""
        # GIVEN
        request = _request({"X-Forwarded-For": "  192.168.1.1  , 10.0.0.1"})

        # WHEN / THEN
        assert get_client_ip(request) == "192.168.1.1"

    def test_falls_back_to_client_host(self):
        """GIVEN no proxy headers WHEN extracting THEN the direct peer host is used."""
        # GIVEN
        request = _request(client_host="127.0.0.1")

        # WHEN / THEN
        assert get_client_ip(request) == "127.0.0.1"

    def test_returns_unknown_when_no_client(self):
        """GIVEN no headers and no client WHEN extracting THEN it is 'unknown'."""
        # GIVEN
        request = _request()

        # WHEN / THEN
        assert get_client_ip(request) == "unknown"

    def test_returns_unknown_for_none_request(self):
        """GIVEN no request WHEN extracting THEN it is 'unknown'."""
        # WHEN / THEN
        assert get_client_ip(None) == "unknown"
