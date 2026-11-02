"""ASGI middleware that rejects over-large request bodies before they are buffered.

Starlette reads the whole request body into memory before validation runs, so a
per-field ``max_length`` on a schema does not protect against a memory-exhaustion
flood. This middleware caps the body at the transport layer instead: it rejects a
declared ``Content-Length`` above the limit up front, and counts bytes for chunked
bodies so no request can buffer more than the limit regardless of the declared size.

Two limits apply. A multipart/form-data body is capped at the largest photo upload plus
framing overhead; every other body is capped at the much lower JSON limit. FastAPI parses
a form before it solves dependencies, so without the multipart ceiling an upload would be
read in full before sign-in could refuse it.

A chunked body cannot be refused up front, so the wrapped ``receive`` raises
:class:`RequestBodyTooLarge` once the count passes the cap. The app cannot be left to
turn that into the answer. FastAPI's body reader turns any exception raised while it
reads the body of a route with a body model into its own 400 "There was an error
parsing the body", with or without other middleware. On a route that reads the body
itself, the ``BaseHTTPMiddleware`` layers between this middleware and the routes wrap
the exception in nested ``ExceptionGroup`` objects, so no handler registered for
:class:`RequestBodyTooLarge` matches it either. So the middleware answers the 413
itself, and drops whatever the app sent after the overflow. ``RequestLoggingMiddleware``
runs outside this middleware, so its access line records that 413 and its
``X-Request-ID`` header is set on it.
"""

import logging
from dataclasses import dataclass

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.services.storage.validation import MAX_FILE_SIZE_BYTES

logger = logging.getLogger("api.request")

# Default cap for buffered request bodies (2 MiB). Comfortably fits the largest
# legitimate JSON payload, a 1000-expert /calculate request, while stopping the
# multi-hundred-MB bodies that would otherwise exhaust worker memory. A multipart body
# has the higher ceiling below.
DEFAULT_MAX_BODY_BYTES = 2 * 1024 * 1024

# Room a multipart body needs on top of the file itself: the boundary lines, the part
# headers and a long filename.
MULTIPART_OVERHEAD_BYTES = 64 * 1024

# Default cap for a multipart body: the largest photo upload plus its framing. The upload
# route still enforces the file size itself and answers a file over it with its own 400.
DEFAULT_MAX_MULTIPART_BYTES = MAX_FILE_SIZE_BYTES + MULTIPART_OVERHEAD_BYTES


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
    """Reject requests whose body exceeds the limit for its kind.

    A multipart/form-data body is held to ``max_multipart_bytes`` and every other body to
    ``max_body_bytes``. A declared ``Content-Length`` over the limit is refused before the
    app runs. A chunked body is counted as it streams; once it passes the limit the read
    is aborted, the app's own answer is discarded and a 413 is sent in its place.

    :param app: The wrapped ASGI application.
    :param max_body_bytes: Largest non-multipart request body accepted, in bytes.
    :param max_multipart_bytes: Largest multipart/form-data request body accepted, in bytes.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
        max_multipart_bytes: int = DEFAULT_MAX_MULTIPART_BYTES,
    ) -> None:
        self._app = app
        self._max_body_bytes = max_body_bytes
        self._max_multipart_bytes = max_multipart_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Enforce the body limit for HTTP requests, passing others through."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        limit = self._limit_for(scope)
        declared = self._declared_length(scope)
        if declared is not None and declared > limit:
            logger.warning(
                "Request body rejected",
                extra={
                    "event": "request_body_rejected",
                    "reason": "declared_content_length",
                    "request_id": scope.get("state", {}).get("request_id"),
                    "declared_bytes": declared,
                    "limit_bytes": limit,
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                },
            )
            await self._send_too_large(send)
            return

        state = _StreamState()
        try:
            await self._app(
                scope, self._capped_receive(receive, state, limit), self._guarded_send(send, state)
            )
        except Exception:
            # The overflow reaches here wrapped in ExceptionGroups, or as whatever the
            # app made of it. Once a response is on the wire there is nothing to replace.
            if not state.overflowed or state.response_started:
                raise

        if not state.overflowed or state.response_started:
            return

        # RequestLoggingMiddleware runs outside this one and stores its id in the shared
        # scope state, so a body refused mid-stream can be tied to its request.
        logger.warning(
            "Request body rejected",
            extra={
                "event": "request_body_rejected",
                "reason": "streamed_overflow",
                "request_id": scope.get("state", {}).get("request_id"),
                "limit_bytes": limit,
                "method": scope.get("method"),
                "path": scope.get("path"),
            },
        )
        await self._send_too_large(send)

    def _limit_for(self, scope: Scope) -> int:
        """Return the body limit that applies to this request, in bytes."""
        return self._max_multipart_bytes if self._is_multipart(scope) else self._max_body_bytes

    @staticmethod
    def _capped_receive(receive: Receive, state: _StreamState, limit: int) -> Receive:
        """Wrap ``receive`` so a body streamed past ``limit`` bytes aborts the request."""
        seen = 0

        async def wrapped() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
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
        """Return whether the request body is multipart/form-data."""
        for name, value in scope.get("headers", []):
            if name == b"content-type":
                return bool(value.lower().startswith(b"multipart/form-data"))
        return False

    @staticmethod
    async def _send_too_large(send: Send) -> None:
        """Emit a 413 response directly, without the downstream app's answer.

        ``RequestLoggingMiddleware`` sets ``X-Request-ID`` on it on the way out.

        :param send: The ASGI send callable.
        """
        body = b'{"detail":"Request body too large"}'
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ]
        await send({"type": "http.response.start", "status": 413, "headers": headers})
        await send({"type": "http.response.body", "body": body})
