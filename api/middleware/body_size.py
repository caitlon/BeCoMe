"""ASGI middleware that rejects over-large request bodies before they are buffered.

Starlette reads the whole request body into memory before validation runs, so a
per-field ``max_length`` on a schema does not protect against a memory-exhaustion
flood. This middleware caps the body at the transport layer instead: it rejects a
declared ``Content-Length`` above the limit up front, and counts bytes for chunked
bodies so no request can buffer more than the limit regardless of the declared size.

A chunked body cannot be refused up front, so the wrapped ``receive`` raises
:class:`RequestBodyTooLarge` once the count passes the cap. That exception never
reaches an exception handler as itself: the ``BaseHTTPMiddleware`` layers between this
middleware and the routes read the body through anyio task groups, which wrap it in a
nested ``ExceptionGroup``, and FastAPI then turns it into a 400 "error parsing the
body". So the middleware answers the 413 itself, and drops whatever the app sent after
the overflow.
"""

import logging
from dataclasses import dataclass

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("api.request")

# Default cap for buffered request bodies (2 MiB). Comfortably fits the largest
# legitimate JSON payload, a 1000-expert /calculate request, while stopping the
# multi-hundred-MB bodies that would otherwise exhaust worker memory. Multipart
# uploads are exempt: the upload route enforces its own streaming size limit.
DEFAULT_MAX_BODY_BYTES = 2 * 1024 * 1024


# A domain event, not an *Error.
class RequestBodyTooLarge(Exception):  # noqa: N818
    """Raised inside the app when a streamed request body passes the configured limit.

    An internal signal that stops the body from being read, not an error the client
    sees: :class:`BodySizeLimitMiddleware` answers the 413 itself.
    """


@dataclass
class _StreamState:
    """What happened to one request, shared by its wrapped ``receive`` and ``send``."""

    overflowed: bool = False
    response_started: bool = False


class BodySizeLimitMiddleware:
    """Reject requests whose body exceeds ``max_body_bytes``.

    A declared ``Content-Length`` over the limit is refused before the app runs. A
    chunked body is counted as it streams; once it passes the limit the read is
    aborted, the app's own answer is discarded and a 413 is sent in its place.

    :param app: The wrapped ASGI application.
    :param max_body_bytes: Largest request body accepted, in bytes.
    """

    def __init__(self, app: ASGIApp, *, max_body_bytes: int = DEFAULT_MAX_BODY_BYTES) -> None:
        self._app = app
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Enforce the body limit for HTTP requests, passing others through."""
        if scope["type"] != "http" or self._is_multipart(scope):
            await self._app(scope, receive, send)
            return

        declared = self._declared_length(scope)
        if declared is not None and declared > self._max_body_bytes:
            # This record carries no request_id: the middleware runs before
            # RequestLoggingMiddleware binds the correlation id.
            # That ordering is the whole point, since the body is refused before
            # anything buffers it, so the missing id is a consequence, not an oversight.
            logger.warning(
                "Request body rejected",
                extra={
                    "event": "request_body_rejected",
                    "reason": "declared_content_length",
                    "declared_bytes": declared,
                    "limit_bytes": self._max_body_bytes,
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                },
            )
            await self._send_too_large(send)
            return

        state = _StreamState()
        try:
            await self._app(
                scope, self._capped_receive(receive, state), self._guarded_send(send, state)
            )
        except Exception:
            # The overflow reaches here wrapped in ExceptionGroups, or as whatever the
            # app made of it. Once a response is on the wire there is nothing to replace.
            if not state.overflowed or state.response_started:
                raise

        if not state.overflowed or state.response_started:
            return

        # RequestLoggingMiddleware runs inside this one and stores its id in the shared
        # scope state, so a body refused mid-stream can be tied to its request.
        request_id = scope.get("state", {}).get("request_id")
        logger.warning(
            "Request body rejected",
            extra={
                "event": "request_body_rejected",
                "reason": "streamed_overflow",
                "request_id": request_id,
                "limit_bytes": self._max_body_bytes,
                "method": scope.get("method"),
                "path": scope.get("path"),
            },
        )
        await self._send_too_large(send, request_id)

    def _capped_receive(self, receive: Receive, state: _StreamState) -> Receive:
        """Wrap ``receive`` so a body streamed past the limit aborts the request."""
        seen = 0

        async def wrapped() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self._max_body_bytes:
                    state.overflowed = True
                    raise RequestBodyTooLarge
            return message

        return wrapped

    @staticmethod
    def _guarded_send(send: Send, state: _StreamState) -> Send:
        """Wrap ``send`` so nothing the app sends after an overflow reaches the client.

        The app answers an aborted body with a 400 of its own. A response that had
        already started before the overflow is left alone, since it cannot be replaced.
        """

        async def wrapped(message: Message) -> None:
            if state.overflowed and not state.response_started:
                return
            if message["type"] == "http.response.start":
                state.response_started = True
            await send(message)

        return wrapped

    @staticmethod
    def _declared_length(scope: Scope) -> int | None:
        """Return the declared ``Content-Length`` in bytes, or ``None`` if absent/invalid."""
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    return int(value)
                except ValueError:
                    return None
        return None

    @staticmethod
    def _is_multipart(scope: Scope) -> bool:
        """Return whether the request is a multipart upload (exempt from this cap)."""
        for name, value in scope.get("headers", []):
            if name == b"content-type":
                return bool(value.lower().startswith(b"multipart/form-data"))
        return False

    @staticmethod
    async def _send_too_large(send: Send, request_id: str | None = None) -> None:
        """Emit a 413 response directly, without the downstream app's answer.

        :param send: The ASGI send callable.
        :param request_id: Correlation id to echo as ``x-request-id``, when one is known.
        """
        body = b'{"detail":"Request body too large"}'
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ]
        if request_id:
            headers.append((b"x-request-id", request_id.encode()))
        await send({"type": "http.response.start", "status": 413, "headers": headers})
        await send({"type": "http.response.body", "body": body})
