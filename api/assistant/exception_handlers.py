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

from api.assistant.agent.generation import raised_at
from api.assistant.errors import (
    AssistantBusyError,
    AssistantError,
    AssistantNotFoundError,
    AssistantRateLimitedError,
    AssistantUnavailableError,
    AssistantUpstreamError,
)

logger = logging.getLogger(__name__)

UNAVAILABLE_DETAIL = "The assistant is temporarily unavailable"
NOT_FOUND_DETAIL = "Project not found"
INTERNAL_ERROR_DETAIL = "Internal server error"


def _log(
    request: Request, exc: Exception, *, event: str, status_code: int, level: int, **fields: str
) -> None:
    """Record a chat error with ids only, never the message text.

    :param request: The request that failed.
    :param exc: The raised assistant error.
    :param event: Machine-readable event name for the record.
    :param status_code: Status the handler answers with.
    :param level: Logging level for the record.
    :param fields: Further fields for the record, such as a ``reason``.
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
            **fields,
        },
    )


def assistant_rate_limited_handler(
    request: Request, exc: AssistantRateLimitedError
) -> JSONResponse:
    """Answer 429 when a user or a client address has spent its hourly assistant budget.

    The body is the same for both. A user's refusal is written as ``assistant_rate_limited``; an
    address's has its own event, ``assistant_address_cap_reached``, with no address, no hash of
    one and no user in the record.

    :param request: FastAPI request.
    :param exc: The raised error.
    :return: A 429 JSON response with a ``Retry-After`` header.
    """
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    _log(
        request,
        exc,
        event=(
            "assistant_address_cap_reached" if exc.reason == "address" else "assistant_rate_limited"
        ),
        status_code=status_code,
        level=logging.WARNING,
    )
    return JSONResponse(
        status_code=status_code,
        content={"detail": "Too many assistant messages. Please try again later."},
        headers={"Retry-After": str(exc.retry_after)},
    )


def assistant_busy_handler(request: Request, exc: AssistantBusyError) -> JSONResponse:
    """Answer 503 with ``Retry-After`` when a turn is refused for load.

    The body is the same fixed text as for an unreachable model server. The record is the
    only one a refusal writes: a WARNING, not an ERROR, since a full assistant is load and not
    a fault, and it names the limit that refused (``process``, ``user`` or ``global``) and no
    user. The global ceiling has an event of its own, ``assistant_global_cap_reached``, since
    it is an hourly spend and not a count of turns running.

    :param request: FastAPI request.
    :param exc: The raised error.
    :return: A 503 JSON response with a ``Retry-After`` header.
    """
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    _log(
        request,
        exc,
        event=(
            "assistant_global_cap_reached"
            if exc.reason == "global"
            else "assistant_concurrency_cap_reached"
        ),
        status_code=status_code,
        level=logging.WARNING,
        reason=exc.reason,
    )
    return JSONResponse(
        status_code=status_code,
        content={"detail": UNAVAILABLE_DETAIL},
        headers={"Retry-After": str(exc.retry_after)},
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


def assistant_not_found_handler(request: Request, exc: AssistantNotFoundError) -> JSONResponse:
    """Answer 404 when a project the caller cannot see escapes a route.

    The service turns this error into ``ProjectNotFoundError`` and the tools catch it, so it
    reaches here only from a path that does neither. The body is the one a missing project
    gets everywhere else, and never the error's text, which names an internal API path.

    :param request: FastAPI request.
    :param exc: The raised error.
    :return: A 404 JSON response.
    """
    status_code = status.HTTP_404_NOT_FOUND
    _log(request, exc, event="assistant_not_found", status_code=status_code, level=logging.WARNING)
    return JSONResponse(status_code=status_code, content={"detail": NOT_FOUND_DETAIL})


def assistant_error_handler(request: Request, exc: AssistantError) -> JSONResponse:
    """Answer 500 for an assistant error that has no handler of its own.

    A subclass with a specific handler never reaches here. One that escapes without a handler
    is a missed case in our code, not a model server that is down or full, so it answers like
    any other unhandled fault: 500 with the generic body, not the retryable 503 of
    :data:`UNAVAILABLE_DETAIL`. The record names where it was raised (see
    :func:`~api.assistant.agent.generation.raised_at`) and never its text. Without this
    handler the error would reach the app's ``BeCoMeAPIError`` handler, which answers 400 with
    the error's text as the detail.

    :param request: FastAPI request.
    :param exc: The raised error.
    :return: A 500 JSON response.
    """
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    _log(
        request,
        exc,
        event="assistant_error",
        status_code=status_code,
        level=logging.ERROR,
        where=raised_at(exc),
    )
    return JSONResponse(status_code=status_code, content={"detail": INTERNAL_ERROR_DETAIL})
