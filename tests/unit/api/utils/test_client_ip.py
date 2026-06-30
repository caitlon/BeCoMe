"""Tests for the shared client-IP extraction helper."""

from unittest.mock import MagicMock, patch

from api.utils.client_ip import get_client_ip

_SECRET = "s3cret-origin-token"  # pragma: allowlist secret


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


def _with_secret(secret: str) -> object:
    """Patch get_settings so cloudflare_origin_secret returns ``secret``."""
    settings = MagicMock()
    settings.cloudflare_origin_secret = secret
    return patch("api.utils.client_ip.get_settings", return_value=settings)


class TestNoOriginSecret:
    """Without a Cloudflare secret (dev/staging/local), use XFF then the peer."""

    def test_returns_first_forwarded_ip(self):
        """GIVEN no secret and an XFF header WHEN extracting THEN the first IP wins."""
        with _with_secret(""):
            request = _request({"X-Forwarded-For": "203.0.113.50, 70.41.3.18"})
            assert get_client_ip(request) == "203.0.113.50"

    def test_strips_whitespace(self):
        """GIVEN no secret and padded XFF WHEN extracting THEN it is trimmed."""
        with _with_secret(""):
            request = _request({"X-Forwarded-For": "  192.168.1.1  , 10.0.0.1"})
            assert get_client_ip(request) == "192.168.1.1"

    def test_ignores_cf_connecting_ip_without_secret(self):
        """GIVEN no secret WHEN only CF-Connecting-IP is set THEN it is not trusted."""
        with _with_secret(""):
            request = _request({"CF-Connecting-IP": "9.9.9.9"}, client_host="127.0.0.1")
            assert get_client_ip(request) == "127.0.0.1"

    def test_falls_back_to_peer(self):
        """GIVEN no secret and no headers WHEN extracting THEN the peer host is used."""
        with _with_secret(""):
            assert get_client_ip(_request(client_host="127.0.0.1")) == "127.0.0.1"

    def test_unknown_without_client(self):
        """GIVEN no secret, no headers, no client WHEN extracting THEN it is 'unknown'."""
        with _with_secret(""):
            assert get_client_ip(_request()) == "unknown"


class TestOriginSecretConfigured:
    """With a Cloudflare secret, trust CF-Connecting-IP only for verified requests."""

    def test_verified_request_uses_cf_connecting_ip(self):
        """GIVEN the matching secret WHEN extracting THEN CF-Connecting-IP wins."""
        with _with_secret(_SECRET):
            request = _request(
                {
                    "X-Origin-Verify": _SECRET,
                    "CF-Connecting-IP": "203.0.113.50",
                    "X-Forwarded-For": "1.2.3.4",
                }
            )
            assert get_client_ip(request) == "203.0.113.50"

    def test_verified_request_strips_whitespace(self):
        """GIVEN the matching secret WHEN the CF IP is padded THEN it is trimmed."""
        with _with_secret(_SECRET):
            request = _request({"X-Origin-Verify": _SECRET, "CF-Connecting-IP": "  203.0.113.50  "})
            assert get_client_ip(request) == "203.0.113.50"

    def test_verified_without_cf_ip_falls_back_to_peer(self):
        """GIVEN the secret but no CF IP WHEN extracting THEN the peer host is used."""
        with _with_secret(_SECRET):
            request = _request({"X-Origin-Verify": _SECRET}, client_host="10.0.0.9")
            assert get_client_ip(request) == "10.0.0.9"

    def test_missing_verify_header_is_unverified(self):
        """GIVEN no verify header WHEN extracting THEN the sentinel is returned."""
        with _with_secret(_SECRET):
            request = _request({"CF-Connecting-IP": "1.2.3.4", "X-Forwarded-For": "5.6.7.8"})
            assert get_client_ip(request) == "unverified-origin"

    def test_wrong_verify_header_is_unverified(self):
        """GIVEN a wrong verify header WHEN extracting THEN the sentinel is returned."""
        with _with_secret(_SECRET):
            request = _request({"X-Origin-Verify": "nope", "CF-Connecting-IP": "1.2.3.4"})
            assert get_client_ip(request) == "unverified-origin"


def test_returns_unknown_for_none_request():
    """GIVEN no request WHEN extracting THEN it is 'unknown'."""
    assert get_client_ip(None) == "unknown"
