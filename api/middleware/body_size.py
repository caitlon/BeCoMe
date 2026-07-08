"""ASGI middleware that rejects over-large request bodies before they are buffered.

Starlette reads the whole request body into memory before validation runs, so a
per-field ``max_length`` on a schema does not protect against a memory-exhaustion
flood. This middleware caps the body at the transport layer instead: it rejects a
declared ``Content-Length`` above the limit up front, and counts bytes for chunked
bodies so no request can buffer more than the limit regardless of the declared size.
"""

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Default cap for buffered request bodies (2 MiB). Comfortably fits the largest
# legitimate JSON payload -- a 1000-expert /calculate request -- while stopping the
# multi-hundred-MB bodies that would otherwise exhaust worker memory. Multipart
# uploads are exempt: the upload route enforces its own streaming size limit.
DEFAULT_MAX_BODY_BYTES = 2 * 1024 * 1024


class RequestBodyTooLarge(Exception):  # noqa: N818 -- domain event, not an *Error
    """Raised when a streamed request body passes the configured byte limit."""


class BodySizeLimitMiddleware:
    """Reject requests whose body exceeds ``max_body_bytes``.

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
            await self._send_too_large(send)
            return

        await self._app(scope, self._capped_receive(receive), send)

    def _capped_receive(self, receive: Receive) -> Receive:
        """Wrap ``receive`` so a body streamed past the limit aborts the request."""
        seen = 0

        async def wrapped() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self._max_body_bytes:
                    raise RequestBodyTooLarge
            return message

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
    async def _send_too_large(send: Send) -> None:
        """Emit a 413 response directly, without invoking the downstream app."""
        body = b'{"detail":"Request body too large"}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def body_too_large_handler(request: Request, exc: Exception) -> Response:
    """Return a 413 when a chunked body streams past the limit mid-request.

    Registered as the handler for :class:`RequestBodyTooLarge`, which is raised from
    the wrapped ``receive`` once a body without a trustworthy ``Content-Length``
    exceeds the cap. Buffering stops at that point, so memory stays bounded.

    :param request: The incoming request.
    :param exc: The raised :class:`RequestBodyTooLarge`.
    :return: A 413 JSON response.
    """
    return JSONResponse(status_code=413, content={"detail": "Request body too large"})
