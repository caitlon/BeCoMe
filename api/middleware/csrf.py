"""CSRF protection for cookie-authenticated mutations.

The check is enforced on any request carrying the session cookie, i.e. a cookie-based
browser client. Programmatic clients that authenticate with a Bearer header send no such
cookie and are unaffected. Pre-session auth endpoints (login, register, refresh, password
reset) are always exempt, so a stale cookie left by a revoked session (e.g. after a
password change) cannot block re-authentication.

``SameSite=Strict`` already stops the session cookies from being sent on cross-site
requests; this check is defense-in-depth against the case ``SameSite`` does not cover.
"Site" means the registrable domain, so a page on any ``becomify.app`` subdomain is
same-site with the API and its requests do carry the session cookies. Such a page can
also *write* cookies for the whole domain, which is why the expected token is derived
from the session (:func:`~api.auth.cookies.csrf_token_for`) rather than read back out of
a cookie: a value the attacker plants, or one minted for a session they do hold, no
longer matches what the server computes for the victim's session.

Deriving it also means the check cannot be switched off by omission. The comparison keys
on the session cookie, so a request that authenticates as somebody is always checked --
where a cookie-versus-header comparison silently passed anything that simply arrived
without the CSRF cookie.
"""

import logging
import secrets

from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from api.auth.cookies import CSRF_HEADER, expected_csrf_token
from api.utils.client_ip import get_client_ip

logger = logging.getLogger("api.security")

# Methods that never change state need no CSRF token (OPTIONS also keeps CORS preflight
# working, since a cross-origin preflight carries no cookies or custom headers).
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

# Pre-session auth endpoints must work without a CSRF token: a client can hold a session
# cookie for a session that was revoked (after a password change, say), and these requests
# establish or refresh a session rather than act on one. Logout is excluded -- it acts on a
# live session and the browser client sends the matching token.
_AUTH_PREFIX = "/api/v1/auth/"
_CSRF_PROTECTED_AUTH_PATHS = frozenset({"/api/v1/auth/logout"})


def _csrf_exempt(path: str) -> bool:
    """Return whether a path is a pre-session auth endpoint exempt from the CSRF check."""
    return path.startswith(_AUTH_PREFIX) and path not in _CSRF_PROTECTED_AUTH_PATHS


class CSRFMiddleware(BaseHTTPMiddleware):
    """Reject cookie-authenticated mutating requests that lack a matching CSRF token."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Validate the session-bound token on cookie-authenticated mutations.

        :param request: Incoming request.
        :param call_next: Downstream handler.
        :return: A 403 response when the CSRF token is missing or wrong, else the
            downstream response.
        """
        if request.method not in _SAFE_METHODS and not _csrf_exempt(request.url.path):
            expected = expected_csrf_token(request)
            if expected is not None:
                header = request.headers.get(CSRF_HEADER)
                if header is None:
                    return self._reject("missing_header", request)
                # Compare as bytes: compare_digest raises TypeError on a non-ASCII str,
                # which would turn a junk header into a 500 instead of this 403.
                if not secrets.compare_digest(header.encode(), expected.encode()):
                    return self._reject("token_mismatch", request)
        return await call_next(request)

    @staticmethod
    def _reject(reason: str, request: Request) -> JSONResponse:
        """Log the refused request and build its 403.

        Neither the presented header nor the expected token reaches the record. The
        expected value is what the check compares against, so logging it would hand
        anyone reading the log the token needed to forge the request just blocked -- and
        because it is derived from the session id, one leaked record would keep working
        for as long as that session lives.

        :param reason: Why the check failed -- ``missing_header`` or ``token_mismatch``.
        :param request: The refused request.
        :return: The 403 response sent to the caller.
        """
        logger.warning(
            "CSRF check failed",
            extra={
                "event": "csrf_rejected",
                "reason": reason,
                "method": request.method,
                "path": request.url.path,
                "ip": get_client_ip(request),
            },
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "CSRF token missing or invalid"},
        )
