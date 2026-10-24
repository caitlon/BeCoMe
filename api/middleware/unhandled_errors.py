"""Turn an exception no handler maps into a 500 inside the middleware stack."""

import sentry_sdk
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.middleware.exception_handlers import unhandled_exception_handler


class UnhandledErrorMiddleware:
    """Answer an unhandled exception with the opaque 500, from inside every other middleware.

    Starlette routes a handler for ``Exception`` to ``ServerErrorMiddleware``, which it
    always places outside the user middleware. A 500 sent from there skips CORS, the
    security headers and the request log, and the browser hides a cross-origin response
    without ``Access-Control-Allow-Origin``, so the SPA saw a network error instead. Added
    first, this middleware sits innermost, just outside the routes, and its 500 travels back
    out through all of them.

    The exception is not re-raised, so it is reported to Sentry here. Once the response
    has started (a stream that fails midway) a 500 can no longer be sent, and the exception
    goes on to ``ServerErrorMiddleware`` as before.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the downstream ASGI app.

        :param app: The application this middleware guards.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run the app and answer a 500 when it raises before responding.

        :param scope: ASGI connection scope.
        :param receive: ASGI receive callable.
        :param send: ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_tracking_start(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_tracking_start)
        except Exception as exc:
            if response_started:
                raise
            sentry_sdk.capture_exception(exc)
            response = unhandled_exception_handler(Request(scope), exc)
            await response(scope, receive, send)
