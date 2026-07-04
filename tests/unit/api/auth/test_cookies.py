"""Tests for the auth-cookie Secure-flag policy."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from api.auth import cookies
from api.config import Environment


def _request(scheme: str) -> MagicMock:
    """Build a stand-in request whose only relevant attribute is the URL scheme."""
    return MagicMock(url=SimpleNamespace(scheme=scheme))


class TestCookiesSecure:
    """cookies_secure is on in production and otherwise follows the request scheme."""

    def test_secure_in_production_regardless_of_scheme(self):
        with patch.object(
            cookies, "get_settings", return_value=SimpleNamespace(environment=Environment.PROD)
        ):
            assert cookies.cookies_secure(_request("http")) is True

    def test_not_secure_over_http_outside_production(self):
        with patch.object(
            cookies, "get_settings", return_value=SimpleNamespace(environment=Environment.TEST)
        ):
            assert cookies.cookies_secure(_request("http")) is False

    def test_secure_over_https_outside_production(self):
        with patch.object(
            cookies, "get_settings", return_value=SimpleNamespace(environment=Environment.DEV)
        ):
            assert cookies.cookies_secure(_request("https")) is True
