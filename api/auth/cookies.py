"""Auth session cookies: names, flags, and set/clear helpers.

Access and refresh tokens are delivered as ``Secure; HttpOnly; SameSite=Strict``
cookies so JavaScript cannot read them (blunts token theft via XSS). A separate,
readable ``csrf_token`` cookie carries the CSRF token: the SPA echoes it in the
``X-CSRF-Token`` header on mutating requests. The same value goes out in an
``X-CSRF-Token`` *response* header, which is the only copy a cross-host SPA can reach
(see :func:`set_csrf_header`). The token also stays in the login response body so
programmatic clients and the test suite can keep using the ``Authorization: Bearer``
header.

The token is derived from the session rather than drawn at random -- see
:func:`csrf_token_for` for why the cookie is a delivery channel and not the thing the
check trusts.
"""

import hmac
import logging
from hashlib import sha256

from fastapi import Request, Response

from api.auth.jwt import session_id_from_access_token
from api.config import Environment, get_settings

# Domain separator mixed into the CSRF HMAC so the digest cannot be replayed as, or
# confused with, any other value keyed on the same secret.
_CSRF_HMAC_CONTEXT = b"csrf:"

logger = logging.getLogger("api.security")

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"

# The refresh cookie is scoped to the auth routes, so the browser only sends it to
# login/refresh/logout instead of on every API call.
REFRESH_COOKIE_PATH = "/api/v1/auth"


def cookies_secure(request: Request) -> bool:
    """Return whether auth cookies should carry the ``Secure`` flag.

    Always on in production; otherwise on only when the request itself arrived over
    HTTPS. This keeps cookies working over plain HTTP for local dev, the pytest client,
    and the HTTP e2e stack (a ``Secure`` cookie is dropped by the browser over HTTP),
    while production behind TLS always gets ``Secure`` cookies.

    :param request: The incoming request, used to read the connection scheme.
    :return: True when cookies must be HTTPS-only.
    """
    if get_settings().environment is Environment.PROD:
        return True
    return request.url.scheme == "https"


def csrf_token_for(sid: str) -> str:
    """Derive the CSRF token that belongs to one session.

    The token is an HMAC of the session id under the application secret, not a random
    value stored alongside it. That is what makes the check survive an attacker who can
    write cookies for the API host -- one sitting on any ``becomify.app`` subdomain, say,
    since ``SameSite`` treats the whole registrable domain as one site and a cookie set
    with ``Domain=becomify.app`` shadows ours.

    Against a plain double-submit check, such an attacker wins twice over: they can plant
    a value they know in the ``csrf_token`` cookie and echo it in the header, and they can
    equally plant a token minted for *their own* session. Deriving it from the victim's
    ``sid`` closes both. The server recomputes the expected value from the session the
    request actually authenticates as, so a token is only ever valid for one session, and
    forging one for a session you do not hold means forging an HMAC.

    The cookie therefore stops being the thing the check trusts and becomes one of two
    delivery channels (the other is the response header); the comparison is against a
    value the server derives, never against something the client sent.

    :param sid: Session id shared by the whole refresh-token rotation family.
    :return: Hex-encoded token, safe to carry in a cookie and a header.
    """
    secret = get_settings().secret_key.encode()
    return hmac.new(secret, _CSRF_HMAC_CONTEXT + sid.encode(), sha256).hexdigest()


def expected_csrf_token(request: Request) -> str | None:
    """Return the CSRF token this request's session must present, if it has one.

    :param request: Incoming request, read for the session cookie.
    :return: The derived token, or None when the request carries no session cookie, the
        cookie is unreadable, or it predates sessions -- in which case there is no
        session to bind a token to and the check does not apply.
    """
    token = request.cookies.get(ACCESS_COOKIE)
    if token is None:
        return None
    sid = session_id_from_access_token(token)
    if sid is None:
        return None
    return csrf_token_for(sid)


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    access_ttl: int,
    refresh_ttl: int,
    secure: bool,
) -> None:
    """Attach the access, refresh, and CSRF cookies to a response.

    :param response: The response to set cookies on.
    :param access_token: Short-lived access token (HttpOnly cookie).
    :param refresh_token: Long-lived refresh token (HttpOnly, auth-scoped cookie).
    :param csrf_token: Double-submit CSRF token (readable cookie).
    :param access_ttl: Access-cookie lifetime in seconds.
    :param refresh_ttl: Refresh- and CSRF-cookie lifetime in seconds.
    :param secure: Whether to set the ``Secure`` flag (see :func:`cookies_secure`).
    """
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
    logger.debug(
        "Auth cookies set",
        extra={
            "event": "auth_cookies_set",
            "secure": secure,
            "access_ttl": access_ttl,
            "refresh_ttl": refresh_ttl,
        },
    )


def set_csrf_header(response: Response, csrf_token: str | None) -> None:
    """Repeat the CSRF token in a response header so a cross-host SPA can read it.

    The ``csrf_token`` cookie carries no ``Domain`` attribute, so it belongs to the API
    host alone. In every deployed environment the SPA is served from a different host and
    ``document.cookie`` shows it nothing, which leaves it unable to fill in the
    ``X-CSRF-Token`` request header the double-submit check demands. The header is the
    copy it can reach; ``CORSMiddleware`` must name it in ``expose_headers`` for the
    browser to hand it over.

    This gives away nothing. The value is meant to be readable by the client that owns the
    session -- that is what lets the SPA send it back in the header -- and CORS answers
    against an explicit origin allow-list, so a hostile origin can no more read the header
    than the cookie. Setting ``Domain=becomify.app`` on the cookie instead would look
    simpler and break the deploys: dev, staging, and production all live under that parent
    and would overwrite each other's token.

    Every value passed here is derived by :func:`csrf_token_for`, so it is a hex digest and
    nothing else. That matters for what this function no longer has to do: it used to echo
    the caller's own ``csrf_token`` cookie back on ``/auth/me``, and Starlette unescapes
    cookies the RFC 2109 way, so ``csrf_token="\\012X-Injected: 1"`` -- every character of
    it legal in a ``Cookie`` header -- parsed into a value carrying a real newline that
    uvicorn's writer would have concatenated into the response unchecked. Deriving the
    token server-side removes that path entirely rather than filtering it.

    :param response: The response to set the header on.
    :param csrf_token: Token to send, or None when the request has no session to derive
        one from (a Bearer client, or an access token minted before sessions existed).
    """
    if csrf_token:
        response.headers[CSRF_HEADER] = csrf_token


def clear_auth_cookies(response: Response) -> None:
    """Delete the access, refresh, and CSRF cookies (used on logout).

    :param response: The response to clear cookies on.
    """
    response.delete_cookie(ACCESS_COOKIE)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE)
    logger.debug("Auth cookies cleared", extra={"event": "auth_cookies_cleared"})
