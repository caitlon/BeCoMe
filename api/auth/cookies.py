"""Auth session cookies: names, flags, and set/clear helpers.

Access and refresh tokens are delivered as ``Secure; HttpOnly; SameSite=Strict``
cookies so JavaScript cannot read them (blunts token theft via XSS). A separate,
readable ``csrf_token`` cookie backs the double-submit CSRF check: the SPA echoes it
in the ``X-CSRF-Token`` header on mutating requests. The token also stays in the login
response body so programmatic clients and the test suite can keep using the
``Authorization: Bearer`` header.
"""

import secrets

from fastapi import Response

from api.config import Environment, get_settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"

# The refresh cookie is scoped to the auth routes, so the browser only sends it to
# login/refresh/logout instead of on every API call.
REFRESH_COOKIE_PATH = "/api/v1/auth"


def cookies_secure() -> bool:
    """Return whether auth cookies should carry the ``Secure`` flag.

    Secure on the deployed profiles (served over HTTPS); off for local dev and the
    pytest client, which both speak plain HTTP so the cookie would otherwise never
    round-trip.

    :return: True when cookies must be HTTPS-only.
    """
    settings = get_settings()
    return settings.environment is not Environment.DEV and not settings.testing


def new_csrf_token() -> str:
    """Return a fresh, high-entropy token for the double-submit CSRF cookie."""
    return secrets.token_urlsafe(32)


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    access_ttl: int,
    refresh_ttl: int,
) -> None:
    """Attach the access, refresh, and CSRF cookies to a response.

    :param response: The response to set cookies on.
    :param access_token: Short-lived access token (HttpOnly cookie).
    :param refresh_token: Long-lived refresh token (HttpOnly, auth-scoped cookie).
    :param csrf_token: Double-submit CSRF token (readable cookie).
    :param access_ttl: Access-cookie lifetime in seconds.
    :param refresh_ttl: Refresh- and CSRF-cookie lifetime in seconds.
    """
    secure = cookies_secure()
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=access_ttl,
        httponly=True,
        secure=secure,
        samesite="strict",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=refresh_ttl,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=secure,
        samesite="strict",
    )
    # Not HttpOnly: the SPA reads it to echo back in the X-CSRF-Token header.
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=refresh_ttl,
        httponly=False,
        secure=secure,
        samesite="strict",
    )


def clear_auth_cookies(response: Response) -> None:
    """Delete the access, refresh, and CSRF cookies (used on logout).

    :param response: The response to clear cookies on.
    """
    response.delete_cookie(ACCESS_COOKIE)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE)
