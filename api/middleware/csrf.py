"""Double-submit CSRF protection for cookie-authenticated mutations.

The check is enforced only when the request carries the readable ``csrf_token`` cookie,
i.e. a cookie-based browser client. Programmatic clients that authenticate with a Bearer
header (and requests made before login) send no such cookie and are unaffected.

``SameSite=Strict`` already stops the session cookies from being sent on cross-site
requests; this double-submit check is defense-in-depth: an attacker who cannot read the
``csrf_token`` cookie value cannot forge the matching ``X-CSRF-Token`` header.
"""

import secrets

from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from api.auth.cookies import CSRF_COOKIE, CSRF_HEADER

# Methods that never change state need no CSRF token (OPTIONS also keeps CORS preflight
# working, since a cross-origin preflight carries no cookies or custom headers).
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class CSRFMiddleware(BaseHTTPMiddleware):
    """Reject cookie-authenticated mutating requests that lack a matching CSRF token."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Validate the double-submit token on cookie-authenticated mutations.

        :param request: Incoming request.
        :param call_next: Downstream handler.
        :return: A 403 response when the CSRF token is missing or wrong, else the
            downstream response.
        """
        if request.method not in _SAFE_METHODS:
            cookie = request.cookies.get(CSRF_COOKIE)
            if cookie is not None:
                header = request.headers.get(CSRF_HEADER)
                if header is None or not secrets.compare_digest(header, cookie):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "CSRF token missing or invalid"},
                    )
        return await call_next(request)
