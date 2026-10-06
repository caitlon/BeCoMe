"""HTTP handlers for the assistant's chat errors.

These are not in ``EXCEPTION_MAP`` on purpose: that map loads in every deployed
process, and the assistant package must not. ``api.main.create_app`` registers them
next to the assistant router, so they exist only when ``assistant_enabled`` is true.
Bodies follow the app's ``{"detail": ...}`` shape, with a fixed public message that
never echoes the error's own text (it can name a host, port or model path).
"""

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse

from api.assistant.errors import (
    AssistantRateLimitedError,
    AssistantUnavailableError,
    AssistantUpstreamError,
)

logger = logging.getLogger(__name__)

UNAVAILABLE_DETAIL = "The assistant is temporarily unavailable"


def _log(request: Request, exc: Exception, *, event: str, status_code: int, level: int) -> None:
    """Record a chat error with ids only, never the message text.

    :param request: The request that failed.
    :param exc: The raised assistant error.
    :param event: Machine-readable event name for the record.
    :param status_code: Status the handler answers with.
    :param level: Logging level for the record.
    """
    logger.log(
        level,
        "%s -> %d",
        type(exc).__name__,
        status_code,
        extra={
            "event": event,
            "request_id": getattr(request.state, "request_id", None),
            "status_code": status_code,
            "path": request.url.path,
            "exception_type": type(exc).__name__,
        },
    )


def assistant_rate_limited_handler(
    request: Request, exc: AssistantRateLimitedError
) -> JSONResponse:
    """Answer 429 when a user has spent their hourly assistant budget.

    :param request: FastAPI request.
    :param exc: The raised error.
    :return: A 429 JSON response.
    """
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    _log(
        request, exc, event="assistant_rate_limited", status_code=status_code, level=logging.WARNING
    )
    return JSONResponse(
        status_code=status_code,
        content={"detail": "Too many assistant messages. Please try again later."},
    )


def assistant_unavailable_handler(request: Request, exc: AssistantUnavailableError) -> JSONResponse:
    """Answer 503 when a local model server cannot be reached.

    :param request: FastAPI request.
    :param exc: The raised error.
    :return: A 503 JSON response.
    """
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    _log(request, exc, event="assistant_unavailable", status_code=status_code, level=logging.ERROR)
    return JSONResponse(status_code=status_code, content={"detail": UNAVAILABLE_DETAIL})


def assistant_upstream_handler(request: Request, exc: AssistantUpstreamError) -> JSONResponse:
    """Answer 503 when the read-only API or a model answers with something unusable.

    The public body matches :func:`assistant_unavailable_handler`; only the log event
    differs, so an operator can tell a down server from a bad answer.

    :param request: FastAPI request.
    :param exc: The raised error.
    :return: A 503 JSON response.
    """
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    _log(
        request, exc, event="assistant_upstream_error", status_code=status_code, level=logging.ERROR
    )
    return JSONResponse(status_code=status_code, content={"detail": UNAVAILABLE_DETAIL})
