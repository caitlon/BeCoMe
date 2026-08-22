"""Tests for the auth-cookie prefixes and attributes, and the CSRF response header."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Response
from starlette.requests import cookie_parser

from api.auth import cookies


def _with_secret(secret: str) -> object:
    """Patch get_settings so the CSRF HMAC is keyed on ``secret``.

    :param secret: Value for ``secret_key``.
    :return: The active patch context manager.
    """
    settings = MagicMock()
    settings.secret_key = secret
    return patch("api.auth.cookies.get_settings", return_value=settings)


def _set_cookie_headers(response: Response) -> dict[str, str]:
    """Return each Set-Cookie header the response carries, keyed by cookie name."""
    return {header.split("=", 1)[0]: header for header in response.headers.getlist("set-cookie")}


class TestCookiePrefixes:
    """The browser enforces the prefixes, so the attributes have to earn them.

    A ``__Host-`` cookie is only accepted with ``Secure``, ``Path=/`` and no ``Domain``;
    a ``__Secure-`` one needs ``Secure``. Get an attribute wrong and the browser does not
    fall back to an ordinary cookie -- it drops the ``Set-Cookie`` entirely, and the
    session silently never starts.
    """

    @pytest.fixture
    def issued(self) -> dict[str, str]:
        """Issue one full set of session cookies and return their Set-Cookie headers."""
        response = Response()
        with _with_secret("a-secret-key-for-tests"):
            cookies.set_auth_cookies(
                response,
                access_token="access",
                refresh_token="refresh",
                csrf_token=cookies.csrf_token_for("sid-1"),
                access_ttl=900,
                refresh_ttl=604800,
            )
        return _set_cookie_headers(response)

    def test_names_carry_the_prefixes(self, issued):
        """GIVEN a session WHEN cookies are set THEN each name carries its prefix."""
        assert cookies.ACCESS_COOKIE.startswith("__Host-")
        assert cookies.CSRF_COOKIE.startswith("__Host-")
        assert cookies.REFRESH_COOKIE.startswith("__Secure-")
        assert set(issued) == {
            cookies.ACCESS_COOKIE,
            cookies.REFRESH_COOKIE,
            cookies.CSRF_COOKIE,
        }

    @pytest.mark.parametrize("name_attr", ["ACCESS_COOKIE", "REFRESH_COOKIE", "CSRF_COOKIE"])
    def test_every_cookie_is_secure(self, issued, name_attr):
        """GIVEN any session cookie WHEN it is set THEN it is marked Secure.

        Both prefixes require it, so this is the attribute whose absence would void the
        whole scheme rather than merely weaken it.
        """
        assert "Secure" in issued[getattr(cookies, name_attr)]

    @pytest.mark.parametrize("name_attr", ["ACCESS_COOKIE", "CSRF_COOKIE"])
    def test_host_cookies_are_root_scoped_and_domainless(self, issued, name_attr):
        """GIVEN a __Host- cookie WHEN it is set THEN it has Path=/ and no Domain."""
        header = issued[getattr(cookies, name_attr)]

        assert "Path=/;" in header or header.rstrip().endswith("Path=/")
        assert "Domain=" not in header

    def test_the_refresh_cookie_keeps_its_narrow_path(self, issued):
        """GIVEN the refresh cookie WHEN it is set THEN it stays scoped to the auth routes.

        This is why it takes ``__Secure-`` rather than ``__Host-``: the latter would force
        ``Path=/`` and hand the refresh token to every request on the site.
        """
        assert f"Path={cookies.REFRESH_COOKIE_PATH}" in issued[cookies.REFRESH_COOKIE]


class TestClearAuthCookies:
    """Deleting a prefixed cookie has to satisfy the prefix rules too."""

    @pytest.fixture
    def cleared(self) -> dict[str, str]:
        """Clear the session cookies and return the resulting Set-Cookie headers."""
        response = Response()
        cookies.clear_auth_cookies(response)
        return _set_cookie_headers(response)

    @pytest.mark.parametrize("name_attr", ["ACCESS_COOKIE", "REFRESH_COOKIE", "CSRF_COOKIE"])
    def test_deletions_are_secure(self, cleared, name_attr):
        """GIVEN a logout WHEN cookies are cleared THEN each deletion carries Secure.

        A deletion is a Set-Cookie like any other, so a prefixed cookie sent without
        ``Secure`` is rejected outright -- and Starlette's ``delete_cookie`` defaults to
        ``secure=False``. Logout would answer 204 with the session cookie still in the
        browser.
        """
        assert "Secure" in cleared[getattr(cookies, name_attr)]

    def test_the_refresh_deletion_matches_the_path_it_was_set_on(self, cleared):
        """GIVEN a logout WHEN the refresh cookie is cleared THEN the path matches.

        Cookies are keyed by name, domain **and** path: a deletion sent for ``/`` would
        leave the one stored under the auth path untouched.
        """
        assert f"Path={cookies.REFRESH_COOKIE_PATH}" in cleared[cookies.REFRESH_COOKIE]


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
