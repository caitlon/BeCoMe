"""Tests for the request body size limit middleware."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from api.middleware.body_size import BodySizeLimitMiddleware, RequestBodyTooLarge
from tests.shared.helpers import captured_log_records


def _client(max_bytes: int) -> TestClient:
    """Build a tiny app guarded by the body-size middleware for testing."""
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=max_bytes)

    @app.post("/echo")
    async def echo(request: Request) -> dict[str, int]:
        body = await request.body()
        return {"length": len(body)}

    return TestClient(app)


class TestBodySizeLimit:
    """The middleware caps buffered request bodies at the configured limit."""

    def test_rejects_body_over_the_limit(self):
        """GIVEN a body larger than the limit WHEN posted THEN it is rejected with 413."""
        response = _client(max_bytes=100).post("/echo", content=b"x" * 200)
        assert response.status_code == 413

    def test_allows_body_within_the_limit(self):
        """GIVEN a body within the limit WHEN posted THEN it passes through."""
        response = _client(max_bytes=100).post("/echo", content=b"x" * 50)
        assert response.status_code == 200
        assert response.json()["length"] == 50

    def test_skips_multipart_uploads(self):
        """GIVEN a multipart upload over the limit WHEN posted THEN it is not rejected here.

        File uploads carry their own streaming size limit in the upload route, so the
        body middleware must not reject legitimate photo uploads that exceed the small
        JSON body cap.
        """
        files = {"file": ("photo.txt", b"y" * 500)}
        response = _client(max_bytes=100).post("/echo", files=files)
        assert response.status_code == 200


class TestChunkedBodyLimit:
    """A body sent without Content-Length is counted as it streams."""

    def test_rejects_chunked_body_over_the_limit(self):
        """
        GIVEN a chunked body larger than the limit
        WHEN it is posted
        THEN the answer is the middleware's 413, not the app's 400 or its own response
        """

        def chunks():
            yield b"x" * 80
            yield b"x" * 80

        response = _client(max_bytes=100).post("/echo", content=chunks())

        assert response.status_code == 413
        assert response.json() == {"detail": "Request body too large"}

    def test_allows_chunked_body_within_the_limit(self):
        """GIVEN a chunked body within the limit WHEN posted THEN it passes through."""

        def chunks():
            yield b"x" * 30
            yield b"x" * 30

        response = _client(max_bytes=100).post("/echo", content=chunks())

        assert response.status_code == 200
        assert response.json()["length"] == 60


_SCOPE: Scope = {"type": "http", "method": "POST", "path": "/echo", "headers": []}


def _chunked_receive(*chunks: bytes) -> Receive:
    """Build a ``receive`` that yields the chunks as streamed ``http.request`` messages."""
    messages: list[Message] = [
        {"type": "http.request", "body": chunk, "more_body": index < len(chunks) - 1}
        for index, chunk in enumerate(chunks)
    ]

    async def receive() -> Message:
        return messages.pop(0)

    return receive


def _collecting_send() -> tuple[Send, list[Message]]:
    """Build a ``send`` that records every message it is given."""
    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    return send, sent


class TestStreamedOverflowOnRawApp:
    """The middleware's overflow handling, driven with a bare ASGI app and no FastAPI."""

    @pytest.mark.asyncio
    async def test_unrelated_exception_propagates_and_nothing_is_sent(self):
        """
        GIVEN an app that raises without reading past the cap
        WHEN the middleware runs it
        THEN the exception propagates and no 413 is sent
        """

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            raise RuntimeError("boom")

        send, sent = _collecting_send()
        middleware = BodySizeLimitMiddleware(app, max_body_bytes=10)

        with pytest.raises(RuntimeError, match="boom"):
            await middleware(_SCOPE, _chunked_receive(b"x" * 5), send)

        assert sent == []

    @pytest.mark.asyncio
    async def test_overflow_after_the_response_started_is_not_replaced(self):
        """
        GIVEN an app that has started its response and then reads past the cap
        WHEN the middleware runs it
        THEN the overflow propagates, the app's start is kept and no 413 is sent
        """

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"a", "more_body": True})
            await receive()
            await receive()

        send, sent = _collecting_send()
        middleware = BodySizeLimitMiddleware(app, max_body_bytes=10)

        with pytest.raises(RequestBodyTooLarge):
            await middleware(_SCOPE, _chunked_receive(b"x" * 6, b"x" * 6), send)

        starts = [m for m in sent if m["type"] == "http.response.start"]
        assert [m["status"] for m in starts] == [200]

    @pytest.mark.asyncio
    async def test_app_that_finishes_its_started_response_after_overflow_is_kept(self):
        """
        GIVEN an app that started a response, caught the overflow and finished the response
        WHEN the middleware runs it
        THEN every message the app sent reaches the client and no 413 is added
        """

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"a", "more_body": True})
            try:
                await receive()
                await receive()
            except RequestBodyTooLarge:
                pass
            await send({"type": "http.response.body", "body": b"b"})

        send, sent = _collecting_send()
        middleware = BodySizeLimitMiddleware(app, max_body_bytes=10)

        await middleware(_SCOPE, _chunked_receive(b"x" * 6, b"x" * 6), send)

        assert [m["type"] for m in sent] == [
            "http.response.start",
            "http.response.body",
            "http.response.body",
        ]
        assert sent[0]["status"] == 200
        assert [m["body"] for m in sent[1:]] == [b"a", b"b"]


class TestBodySizeWiring:
    """The application factory installs the body-size middleware."""

    def test_app_registers_body_size_middleware(self):
        """GIVEN the full application WHEN created THEN the body-size middleware is present."""
        from api.main import create_app

        app = create_app()
        assert any(middleware.cls is BodySizeLimitMiddleware for middleware in app.user_middleware)

    def test_real_app_rejects_oversized_body_before_validation(self):
        """GIVEN the real app WHEN a body over the default cap hits /calculate THEN it is 413.

        Proves the guard runs ahead of the route: an oversized body is rejected before the
        route's schema validation runs, so the payload never buffers into memory.
        """
        from api.main import create_app
        from api.middleware.body_size import DEFAULT_MAX_BODY_BYTES

        client = TestClient(create_app())
        oversized = b'{"experts":"' + b"x" * (DEFAULT_MAX_BODY_BYTES + 16) + b'"}'
        response = client.post(
            "/api/v1/calculate",
            content=oversized,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413

    def test_real_app_rejects_a_chunked_body_over_the_cap(self):
        """
        GIVEN the real app and a JSON body sent in chunks, with no Content-Length
        WHEN it streams past the default cap on /calculate
        THEN the answer is a 413 that carries the request id, and one streamed_overflow
            record with that request id is written
        """
        from api.main import create_app
        from api.middleware.body_size import DEFAULT_MAX_BODY_BYTES

        def chunks():
            yield b'{"experts":"'
            for _ in range(DEFAULT_MAX_BODY_BYTES // 65536 + 2):
                yield b"x" * 65536
            yield b'"}'

        client = TestClient(create_app())
        with captured_log_records("api.request") as records:
            response = client.post(
                "/api/v1/calculate",
                content=chunks(),
                headers={"Content-Type": "application/json", "X-Request-ID": "req-413"},
            )

        assert response.status_code == 413
        assert response.json() == {"detail": "Request body too large"}
        assert response.headers.get("x-request-id") == "req-413"
        overflow = [r for r in records if getattr(r, "event", None) == "request_body_rejected"]
        assert len(overflow) == 1
        assert overflow[0].reason == "streamed_overflow"  # type: ignore[attr-defined]
        assert overflow[0].request_id == "req-413"  # type: ignore[attr-defined]
