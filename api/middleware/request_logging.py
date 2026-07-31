"""Request/response logging middleware with correlation IDs."""

import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.logging_context import reset_request_id, set_request_id
from api.utils.client_ip import get_client_ip

logger = logging.getLogger("api.request")

REQUEST_ID_HEADER = "X-Request-ID"

# An inbound correlation ID is echoed back on the response and written to every log
# record of the request, so it is only reused when it looks like one: printable ASCII
# from a conservative alphabet, and short. Anything else is replaced by a fresh UUID
# rather than rejected, since a malformed header should not fail the request.
_MAX_REQUEST_ID_LENGTH = 128
_REQUEST_ID_PATTERN = re.compile(rf"\A[A-Za-z0-9._:-]{{1,{_MAX_REQUEST_ID_LENGTH}}}\Z")

# Requests slower than this are logged at WARNING instead of INFO.
_SLOW_REQUEST_MS = 1000.0

# Noisy endpoints excluded from request logging.
_SKIP_PATHS = frozenset({"/api/v1/health"})


def _correlation_id(inbound: str | None) -> str:
    """Return a usable correlation ID for this request.

    The caller-supplied value is honoured only when it matches
    :data:`_REQUEST_ID_PATTERN`, so an oversized or exotic header cannot be echoed
    back on the response or smuggled into log records. Anything else silently
    becomes a fresh UUID.

    :param inbound: Raw ``X-Request-ID`` header value, or None when absent.
    :return: The inbound ID when well-formed, otherwise a new UUID4 string.

    >>> _correlation_id("abc-123")
    'abc-123'
    >>> _correlation_id("x" * 200) == "x" * 200
    False
    """
    if inbound is not None and _REQUEST_ID_PATTERN.match(inbound):
        return inbound
    return str(uuid.uuid4())


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Assign a correlation ID, log each request/response, and time it.

    A request ID is taken from the inbound ``X-Request-ID`` header or generated,
    stored on ``request.state.request_id`` for downstream handlers, bound to the
    logging context so every ``api.*`` record of this request carries it, and
    echoed back on the response. Request bodies and the ``Authorization`` header
    are never logged.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Log the request, delegate, then log the timed response.

        :param request: Incoming request; its ``X-Request-ID`` header is reused
            as the correlation ID when it is well-formed, otherwise a new one is
            generated.
        :param call_next: Downstream handler that produces the response.
        :return: The downstream response with the ``X-Request-ID`` header set.
        """
        request_id = _correlation_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        path = request.url.path
        token = set_request_id(request_id)
        try:
            if path in _SKIP_PATHS:
                response = await call_next(request)
                response.headers[REQUEST_ID_HEADER] = request_id
                return response

            logger.info(
                "%s %s",
                request.method,
                path,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "ip": get_client_ip(request),
                },
            )

            start = perf_counter()
            response = await call_next(request)
            duration_ms = (perf_counter() - start) * 1000.0

            level = logging.WARNING if duration_ms > _SLOW_REQUEST_MS else logging.INFO
            logger.log(
                level,
                "%s %s %d %.0fms",
                request.method,
                path,
                response.status_code,
                duration_ms,
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 1),
                },
            )

            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            reset_request_id(token)
