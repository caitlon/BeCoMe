"""Tests for the CSRF exempt-path policy and the per-request expected token."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import jwt

from api.auth.cookies import ACCESS_COOKIE, csrf_token_for, expected_csrf_token
from api.auth.jwt import ALGORITHM, create_access_token
from api.config import get_settings
from api.middleware.csrf import _csrf_exempt


def _request(cookies: dict[str, str]) -> MagicMock:
    """Build a stand-in request carrying the given cookies."""
    return MagicMock(cookies=cookies)


class TestCsrfExempt:
    """Pre-session auth endpoints are exempt from CSRF; logout and app routes are not."""

    def test_login_is_exempt(self):
        assert _csrf_exempt("/api/v1/auth/login") is True

    def test_refresh_is_exempt(self):
        assert _csrf_exempt("/api/v1/auth/refresh") is True

    def test_logout_is_not_exempt(self):
        assert _csrf_exempt("/api/v1/auth/logout") is False

    def test_app_route_is_not_exempt(self):
        assert _csrf_exempt("/api/v1/projects") is False


class TestExpectedCsrfToken:
    """What the middleware compares the X-CSRF-Token header against."""

    def test_derives_the_token_for_the_session_cookie(self):
        """GIVEN a session cookie WHEN deriving THEN it matches that session's token."""
        token = create_access_token(uuid4(), sid="session-1")

        assert expected_csrf_token(_request({ACCESS_COOKIE: token})) == csrf_token_for("session-1")

    def test_no_session_cookie_means_no_check(self):
        """GIVEN a Bearer client WHEN deriving THEN None, so the check does not apply."""
        assert expected_csrf_token(_request({})) is None

    def test_unreadable_cookie_means_no_check(self):
        """GIVEN junk in the session cookie WHEN deriving THEN None.

        The request cannot authenticate either, so it is refused a moment later with 401.
        """
        assert expected_csrf_token(_request({ACCESS_COOKIE: "not-a-jwt"})) is None

    def test_token_without_a_session_means_no_check(self):
        """GIVEN an access token predating sessions WHEN deriving THEN None.

        Pins a deliberate gap rather than an oversight: such a token carries no sid to
        bind a value to, so the check has nothing to compare. It is reachable only for
        the 15 minutes an access token minted before sessions existed stays valid, and
        the first refresh migrates the client onto a session-bearing family.
        """
        legacy = jwt.encode(
            {
                "sub": str(uuid4()),
                "exp": datetime.now(UTC) + timedelta(minutes=15),
                "iat": datetime.now(UTC),
                "jti": "j",
                "type": "access",
            },
            get_settings().secret_key,
            algorithm=ALGORITHM,
        )

        assert expected_csrf_token(_request({ACCESS_COOKIE: legacy})) is None
