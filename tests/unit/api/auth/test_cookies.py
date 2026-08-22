"""Tests for the auth-cookie Secure-flag policy and the CSRF response header."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import Response
from starlette.requests import cookie_parser

from api.auth import cookies
from api.config import Environment


def _request(scheme: str) -> MagicMock:
    """Build a stand-in request whose only relevant attribute is the URL scheme."""
    return MagicMock(url=SimpleNamespace(scheme=scheme))


def _with_secret(secret: str) -> object:
    """Patch get_settings so the CSRF HMAC is keyed on ``secret``.

    :param secret: Value for ``secret_key``.
    :return: The active patch context manager.
    """
    settings = MagicMock()
    settings.secret_key = secret
    return patch("api.auth.cookies.get_settings", return_value=settings)


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


class TestCsrfTokenFor:
    """The CSRF token is derived from the session, not drawn at random."""

    def test_is_stable_for_one_session(self):
        """GIVEN one sid WHEN deriving twice THEN both calls agree."""
        with _with_secret("a-secret-key-for-tests"):
            assert cookies.csrf_token_for("sid-1") == cookies.csrf_token_for("sid-1")

    def test_differs_between_sessions(self):
        """GIVEN two sids WHEN deriving THEN the tokens differ.

        This is what stops a token minted for the attacker's own session from being
        replayed against a victim's.
        """
        with _with_secret("a-secret-key-for-tests"):
            assert cookies.csrf_token_for("sid-1") != cookies.csrf_token_for("sid-2")

    def test_depends_on_the_secret(self):
        """GIVEN one sid under two secrets WHEN deriving THEN the tokens differ.

        Forging a token for a session you do not hold means forging an HMAC, so the
        secret has to be what the value hangs on.
        """
        with _with_secret("secret-one"):
            first = cookies.csrf_token_for("sid-1")
        with _with_secret("secret-two"):
            second = cookies.csrf_token_for("sid-1")

        assert first != second

    def test_is_header_safe(self):
        """GIVEN any sid WHEN deriving THEN the token is hex and carries no separators.

        The value goes into a response header, and uvicorn's writer does not validate
        header values. A hex digest cannot carry the newline that would split a response,
        which is why the header helper no longer filters what it is given.
        """
        with _with_secret("a-secret-key-for-tests"):
            token = cookies.csrf_token_for('"\\012X-Injected: 1"')

        assert len(token) == 64
        assert all(c in "0123456789abcdef" for c in token)


class TestSetCsrfHeader:
    """The derived CSRF token is repeated in a response header."""

    def test_sends_the_token(self):
        """A derived token goes back out unchanged."""
        response = Response()
        with _with_secret("a-secret-key-for-tests"):
            token = cookies.csrf_token_for("sid-1")

        cookies.set_csrf_header(response, token)

        assert response.headers[cookies.CSRF_HEADER] == token

    def test_omits_the_header_when_there_is_no_session(self):
        """A request with no session to derive a token from gets no header."""
        response = Response()

        cookies.set_csrf_header(response, None)

        assert cookies.CSRF_HEADER not in response.headers

    def test_the_vector_the_old_echo_exposed_is_real(self):
        """Starlette's cookie unescaping really does yield a newline-bearing value.

        Kept as the reason ``/auth/me`` no longer hands the caller's own cookie back:
        every character below is legal in a ``Cookie`` header, and Starlette applies the
        RFC 2109 octal unescape and returns an actual newline. Deriving the token
        server-side removes the path rather than filtering it.
        """
        parsed = cookie_parser('csrf_token="\\012X-Injected: 1"')

        assert parsed["csrf_token"] == "\nX-Injected: 1"
