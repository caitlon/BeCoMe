"""Request/response logging middleware with correlation IDs."""

import logging
import uuid
from collections.abc import Awaitable, Callable
from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("api.request")

REQUEST_ID_HEADER = "X-Request-ID"

# Requests slower than this are logged at WARNING instead of INFO.
_SLOW_REQUEST_MS = 1000.0

# Noisy endpoints excluded from request logging.
_SKIP_PATHS = frozenset({"/api/v1/health"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Assign a correlation ID, log each request/response, and time it.

    A request ID is taken from the inbound ``X-Request-ID`` header or generated,
    stored on ``request.state.request_id`` for downstream handlers, and echoed
    back on the response. Request bodies and the ``Authorization`` header are
    never logged.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Log the request, delegate, then log the timed response."""
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        path = request.url.path

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
                "ip": _client_ip(request),
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


def _client_ip(request: Request) -> str:
    """Extract the client IP, honouring a reverse-proxy forwarded header.

    :param request: Incoming request.
    :return: Client IP address, or ``"unknown"`` when unavailable.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
