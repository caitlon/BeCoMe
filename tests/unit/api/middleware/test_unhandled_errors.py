"""Tests for the middleware that turns an unmapped exception into a 500."""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.types import Message, Receive, Scope, Send

from api.middleware.unhandled_errors import UnhandledErrorMiddleware

CAPTURE_PATH = "api.middleware.unhandled_errors.sentry_sdk.capture_exception"


def _http_scope() -> Scope:
    """Build a minimal HTTP scope."""
    return {
        "type": "http",
        "method": "GET",
        "path": "/boom",
        "raw_path": b"/boom",
        "query_string": b"",
        "headers": [],
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
    }


async def _receive() -> Message:
    """Return an empty request body."""
    return {"type": "http.request", "body": b"", "more_body": False}


class _Collector:
    """Collect the messages the middleware sends."""

    def __init__(self) -> None:
        self.messages: list[Message] = []

    async def __call__(self, message: Message) -> None:
        self.messages.append(message)


async def _run(inner: "object", scope: Scope, collector: _Collector) -> None:
    """Run the middleware around ``inner`` and send into ``collector``."""
    middleware = UnhandledErrorMiddleware(inner)  # type: ignore[arg-type]
    receive: Receive = _receive
    send: Send = collector
    await middleware(scope, receive, send)


class TestUnhandledErrorMiddleware:
    """The middleware answers a 500 only when nothing has been sent yet."""

    @pytest.mark.asyncio
    async def test_raise_before_response_sends_500_and_reports(self):
        """GIVEN an app raising before responding WHEN called THEN a 500 is sent, not raised."""
        error = RuntimeError("boom")

        async def inner(scope: Scope, receive: Receive, send: Send) -> None:
            raise error

        collector = _Collector()
        with patch(CAPTURE_PATH) as capture:
            await _run(inner, _http_scope(), collector)

        capture.assert_called_once_with(error)
        starts = [m for m in collector.messages if m["type"] == "http.response.start"]
        assert len(starts) == 1
        assert starts[0]["status"] == 500
        body = b"".join(m.get("body", b"") for m in collector.messages)
        assert json.loads(body) == {"detail": "Internal server error"}

    @pytest.mark.asyncio
    async def test_raise_after_response_started_reraises(self):
        """GIVEN an app raising after the response started WHEN called THEN it is re-raised."""

        async def inner(scope: Scope, receive: Receive, send: Send) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            raise RuntimeError("midway")

        collector = _Collector()
        with patch(CAPTURE_PATH) as capture, pytest.raises(RuntimeError, match="midway"):
            await _run(inner, _http_scope(), collector)

        capture.assert_not_called()
        starts = [m for m in collector.messages if m["type"] == "http.response.start"]
        assert len(starts) == 1
        assert starts[0]["status"] == 200

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_straight_through(self):
        """GIVEN a lifespan scope WHEN called THEN the inner app gets the same scope."""
        scope: Scope = {"type": "lifespan"}
        inner = MagicMock()

        async def inner_app(scope: Scope, receive: Receive, send: Send) -> None:
            inner(scope)

        await _run(inner_app, scope, _Collector())

        inner.assert_called_once_with(scope)

    @pytest.mark.asyncio
    async def test_non_http_scope_exception_propagates(self):
        """GIVEN a lifespan scope and a raising app WHEN called THEN the error propagates."""

        async def inner(scope: Scope, receive: Receive, send: Send) -> None:
            raise RuntimeError("startup failed")

        with patch(CAPTURE_PATH) as capture, pytest.raises(RuntimeError, match="startup failed"):
            await _run(inner, {"type": "lifespan"}, _Collector())

        capture.assert_not_called()

    @pytest.mark.asyncio
    async def test_normal_response_passes_through_unchanged(self):
        """GIVEN an app that responds normally WHEN called THEN its messages are unchanged."""
        expected: list[Message] = [
            {"type": "http.response.start", "status": 200, "headers": [(b"x-a", b"1")]},
            {"type": "http.response.body", "body": b"ok", "more_body": False},
        ]

        async def inner(scope: Scope, receive: Receive, send: Send) -> None:
            for message in expected:
                await send(message)

        collector = _Collector()
        with patch(CAPTURE_PATH) as capture:
            await _run(inner, _http_scope(), collector)

        assert collector.messages == expected
        capture.assert_not_called()
