"""HTTP response that streams a stored object and always releases it."""

from collections.abc import Mapping

from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from api.services.storage.stored_object import StoredObject


class StoredObjectResponse(StreamingResponse):
    """Stream a stored object's body, releasing its connection on every exit path.

    Plain ``StreamingResponse`` is not enough on its own. Starlette has two ways of
    handling a client that goes away, and only one of them runs the response's own
    cleanup hook: the older branch watches for a disconnect message and finishes
    normally, while the newer one turns a failed write into an exception and simply
    abandons the body iterator. On that branch the generator's ``finally`` waits on
    garbage collection of a suspended async generator, which is not prompt and may
    not happen at all, so the bucket connection is never given back. Wrapping the
    whole ASGI call in a ``finally`` covers both branches.

    :param stored: Open handle whose body becomes the response body.
    :param headers: Extra response headers, such as caching directives.
    """

    def __init__(self, stored: StoredObject, headers: Mapping[str, str] | None = None) -> None:
        """Build the response from an open handle and its reported metadata."""
        merged = dict(headers or {})
        # A declared size lets the browser show real progress instead of falling back
        # to chunked transfer. Absent only when the backend omits the length.
        if stored.content_length is not None:
            merged["Content-Length"] = str(stored.content_length)
        super().__init__(stored.chunks(), media_type=stored.content_type, headers=merged)
        self._stored = stored

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Write the response, then release the handle whatever happened.

        :param scope: ASGI connection scope.
        :param receive: ASGI receive channel.
        :param send: ASGI send channel.
        """
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._stored.close()
