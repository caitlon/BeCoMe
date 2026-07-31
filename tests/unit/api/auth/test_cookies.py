"""Tests for the auth-cookie Secure-flag policy and the CSRF response header."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Response
from starlette.requests import cookie_parser

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


class TestSetCsrfHeader:
    """The CSRF token is repeated in a response header, and only when it is safe to."""

    def test_echoes_a_minted_token(self):
        """A freshly minted token goes back out unchanged."""
        response = Response()
        token = cookies.new_csrf_token()

        cookies.set_csrf_header(response, token)

        assert response.headers[cookies.CSRF_HEADER] == token

    def test_omits_the_header_when_there_is_no_token(self):
        """A request without the CSRF cookie gets a response without the header."""
        response = Response()

        cookies.set_csrf_header(response, None)

        assert cookies.CSRF_HEADER not in response.headers

    @pytest.mark.parametrize(
        "value",
        ["", "\nX-Injected: 1", "token\r\nX-Injected: 1", "caf\xe9", "tok\x00en"],
        ids=["empty", "newline", "crlf", "non-ascii", "null"],
    )
    def test_refuses_a_value_outside_printable_ascii(self, value):
        """A cookie the client chose never decides what goes into a response header.

        On the ``/auth/me`` path the echoed value comes straight from the request, and
        uvicorn's httptools writer does not validate header values, so a newline in one
        would split the response.
        """
        response = Response()

        cookies.set_csrf_header(response, value)

        assert cookies.CSRF_HEADER not in response.headers

    def test_the_vector_it_guards_against_is_reachable_from_a_real_cookie(self):
        """Starlette's cookie unescaping really does yield a newline-bearing value.

        Pins the premise of the check above, which would otherwise be theatre. Every
        character of the header below is legal in a ``Cookie`` header; Starlette applies
        the RFC 2109 octal unescape and hands back an actual newline.
        """
        parsed = cookie_parser('csrf_token="\\012X-Injected: 1"')

        assert parsed["csrf_token"] == "\nX-Injected: 1"
