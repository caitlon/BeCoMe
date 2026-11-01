"""Tests for the request body size limit middleware."""

import asyncio
import logging
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from api.auth.dependencies import get_current_user_fresh
from api.db.models import User
from api.dependencies import get_storage_service, get_user_service
from api.main import create_app
from api.middleware.body_size import (
    DEFAULT_MAX_BODY_BYTES,
    DEFAULT_MAX_MULTIPART_BYTES,
    BodySizeLimitMiddleware,
    RequestBodyTooLarge,
)
from api.middleware.request_logging import RequestLoggingMiddleware
from api.services.storage.base import StorageService
from api.services.storage.validation import MAX_FILE_SIZE_BYTES
from tests.shared.helpers import captured_log_records


def _client(max_bytes: int, max_multipart_bytes: int | None = None) -> TestClient:
    """Build a tiny app guarded by the body-size middleware for testing."""
    app = FastAPI()
    if max_multipart_bytes is None:
        app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=max_bytes)
    else:
        app.add_middleware(
            BodySizeLimitMiddleware,
            max_body_bytes=max_bytes,
            max_multipart_bytes=max_multipart_bytes,
        )

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

    def test_multipart_body_has_its_own_higher_ceiling(self):
        """
        GIVEN a multipart upload above the JSON cap and below the multipart ceiling
        WHEN it is posted
        THEN it passes through, so the JSON cap does not refuse a photo upload
        """
        files = {"file": ("photo.txt", b"y" * 500)}
        response = _client(max_bytes=100, max_multipart_bytes=2000).post("/echo", files=files)
        assert response.status_code == 200

    def test_rejects_multipart_body_over_the_multipart_ceiling(self):
        """
        GIVEN a multipart upload larger than the multipart ceiling
        WHEN it is posted with a Content-Length
        THEN it is refused with 413 and the log record names the ceiling that applied
        """
        files = {"file": ("photo.txt", b"y" * 500)}
        with captured_log_records("api.request") as records:
            response = _client(max_bytes=100, max_multipart_bytes=300).post("/echo", files=files)

        assert response.status_code == 413
        rejected = [r for r in records if getattr(r, "event", None) == "request_body_rejected"]
        assert len(rejected) == 1
        assert rejected[0].reason == "declared_content_length"  # type: ignore[attr-defined]
        assert rejected[0].limit_bytes == 300  # type: ignore[attr-defined]

    def test_rejects_chunked_multipart_body_over_the_multipart_ceiling(self):
        """
        GIVEN a chunked multipart upload that streams past the multipart ceiling
        WHEN it is posted
        THEN it is refused with 413 and the log record names the ceiling that applied
        """

        def chunks():
            yield b"--b\r\n"
            yield b"y" * 200
            yield b"y" * 200

        with captured_log_records("api.request") as records:
            response = _client(max_bytes=100, max_multipart_bytes=300).post(
                "/echo",
                content=chunks(),
                headers={"Content-Type": "multipart/form-data; boundary=b"},
            )

        assert response.status_code == 413
        rejected = [r for r in records if getattr(r, "event", None) == "request_body_rejected"]
        assert len(rejected) == 1
        assert rejected[0].reason == "streamed_overflow"  # type: ignore[attr-defined]
        assert rejected[0].limit_bytes == 300  # type: ignore[attr-defined]

    def test_json_body_keeps_the_json_cap_when_the_multipart_ceiling_is_higher(self):
        """
        GIVEN a non-multipart body above the JSON cap and below the multipart ceiling
        WHEN it is posted
        THEN it is refused, since only multipart gets the higher ceiling
        """
        response = _client(max_bytes=100, max_multipart_bytes=2000).post(
            "/echo", content=b"x" * 500
        )
        assert response.status_code == 413

    def test_default_multipart_ceiling_covers_the_photo_limit_plus_framing(self):
        """
        GIVEN the middleware without an explicit multipart ceiling
        WHEN a multipart upload far above the JSON cap but within the photo limit is posted
        THEN it passes, and the default ceiling sits above the photo limit
        """
        files = {"file": ("photo.txt", b"y" * 500)}
        response = _client(max_bytes=100).post("/echo", files=files)

        assert response.status_code == 200
        assert DEFAULT_MAX_MULTIPART_BYTES > MAX_FILE_SIZE_BYTES


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
        app = create_app()
        assert any(middleware.cls is BodySizeLimitMiddleware for middleware in app.user_middleware)

    def test_real_app_rejects_oversized_body_before_validation(self):
        """GIVEN the real app WHEN a body over the default cap hits /calculate THEN it is 413.

        Proves the guard runs ahead of the route: an oversized body is rejected before the
        route's schema validation runs, so the payload never buffers into memory.
        """
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


# ---- the real app, driven so the bytes pulled from receive are counted ----

_CHUNK = 64 * 1024
_BOUNDARY = b"bcmtestbound"
_MULTIPART_TYPE = b"multipart/form-data; boundary=" + _BOUNDARY
_PHOTO_PATH = "/api/v1/users/me/photo"


def _multipart_head(filename: str = "a.jpg") -> bytes:
    return (
        b"--"
        + _BOUNDARY
        + b'\r\nContent-Disposition: form-data; name="file"; filename="'
        + filename.encode()
        + b'"\r\nContent-Type: image/jpeg\r\n\r\n'
    )


_MULTIPART_TAIL = b"\r\n--" + _BOUNDARY + b"--\r\n"


def _multipart_chunks(file_size: int) -> list[bytes]:
    """Frame ``file_size`` bytes of file content as a multipart body in 64 KiB chunks."""
    full, rest = divmod(file_size, _CHUNK)
    body = [_multipart_head(), *([b"y" * _CHUNK] * full)]
    if rest:
        body.append(b"y" * rest)
    body.append(_MULTIPART_TAIL)
    return body


def _json_chunks(size: int) -> list[bytes]:
    """Build a JSON-looking body of about ``size`` bytes in 64 KiB chunks."""
    return [b'{"experts":"', *([b"x" * _CHUNK] * (size // _CHUNK)), b'"}']


@dataclass
class _Outcome:
    """What one driven request produced."""

    status: int
    headers: dict[str, str]
    bytes_read: int
    records: list[logging.LogRecord]

    def access_records(self, request_id: str) -> list[logging.LogRecord]:
        """The request-log lines that carry a status code for this request."""
        return [
            r
            for r in self.records
            if getattr(r, "request_id", None) == request_id and hasattr(r, "status_code")
        ]

    def rejection_records(self, request_id: str) -> list[logging.LogRecord]:
        """The body-size rejection records for this request."""
        return [
            r
            for r in self.records
            if getattr(r, "event", None) == "request_body_rejected"
            and getattr(r, "request_id", None) == request_id
        ]


async def _drive(
    app: FastAPI,
    path: str,
    chunks: Iterable[bytes],
    headers: list[tuple[bytes, bytes]],
    *,
    declared: bool,
) -> _Outcome:
    """Call the ASGI app directly, counting the body bytes it pulls from ``receive``.

    TestClient hands the whole body over as one message, so it cannot show how much of
    a body the app read before it refused. Here the body arrives in the given chunks.
    """
    pending = deque(chunks)
    all_headers = [(b"host", b"testserver"), *headers]
    if declared:
        all_headers.append((b"content-length", str(sum(map(len, pending))).encode()))
    read = 0
    status = 0
    response_headers: dict[str, str] = {}
    done = asyncio.Event()

    async def receive() -> Message:
        nonlocal read
        if pending:
            chunk = pending.popleft()
            read += len(chunk)
            return {"type": "http.request", "body": chunk, "more_body": bool(pending)}
        await done.wait()
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]
            response_headers.update({k.decode(): v.decode() for k, v in message["headers"]})
        if message["type"] == "http.response.body" and not message.get("more_body"):
            done.set()

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": all_headers,
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }
    with captured_log_records("api.request") as records:
        await app(scope, receive, send)
    return _Outcome(status, response_headers, read, records)


class TestMultipartCeilingOnRealApp:
    """A multipart body is capped before sign-in or the route runs."""

    @pytest.mark.asyncio
    async def test_declared_multipart_over_the_ceiling_is_refused_unread(self):
        """
        GIVEN a multipart upload past the ceiling that declares its Content-Length
        WHEN it is posted to the photo route with no token
        THEN the answer is a 413 and none of the body was read
        """
        chunks = _multipart_chunks(2 * DEFAULT_MAX_MULTIPART_BYTES)

        outcome = await _drive(
            create_app(),
            _PHOTO_PATH,
            chunks,
            [(b"content-type", _MULTIPART_TYPE)],
            declared=True,
        )

        assert outcome.status == 413
        assert outcome.bytes_read == 0

    @pytest.mark.asyncio
    async def test_chunked_multipart_over_the_ceiling_is_cut_off(self):
        """
        GIVEN a chunked multipart upload past the ceiling
        WHEN it is posted to the photo route with no token
        THEN the answer is a 413 and reading stopped within one chunk of the ceiling
        """
        chunks = _multipart_chunks(4 * DEFAULT_MAX_MULTIPART_BYTES)

        outcome = await _drive(
            create_app(),
            _PHOTO_PATH,
            chunks,
            [(b"content-type", _MULTIPART_TYPE)],
            declared=False,
        )

        assert outcome.status == 413
        assert outcome.bytes_read <= DEFAULT_MAX_MULTIPART_BYTES + _CHUNK
        assert outcome.bytes_read < sum(map(len, chunks)) // 2


@pytest.fixture
def photo_app():
    """The real app with the sign-in, the user service and storage faked for the photo route."""
    user = User(
        email="photo@example.com", hashed_password="x", first_name="Photo", last_name="Taker"
    )
    user_service = MagicMock()
    user_service.update_photo_url.return_value = user
    storage = MagicMock(spec=StorageService)
    storage.upload.return_value = "profiles/test/deadbeef0001.jpg"

    app = create_app()
    app.dependency_overrides[get_current_user_fresh] = lambda: user
    app.dependency_overrides[get_user_service] = lambda: user_service
    app.dependency_overrides[get_storage_service] = lambda: storage
    return app, storage


def _photo_file(size: int) -> bytes:
    """A JPEG that passes validation, padded with trailing bytes to ``size``."""
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (8, 8), 120).save(buffer, format="JPEG")
    jpeg = buffer.getvalue()
    return jpeg + b"\x00" * (size - len(jpeg))


class TestPhotoRouteBehindTheCeiling:
    """The higher multipart ceiling lets real uploads through and leaves the route's check."""

    def test_a_file_at_the_photo_limit_with_a_long_filename_reaches_the_route(self, photo_app):
        """
        GIVEN a file of exactly the photo limit with a 255-character filename
        WHEN it is uploaded
        THEN the multipart framing fits under the ceiling and the route stores the photo
        """
        app, storage = photo_app
        filename = "a" * 251 + ".jpg"

        response = TestClient(app).post(
            _PHOTO_PATH,
            files={"file": (filename, _photo_file(MAX_FILE_SIZE_BYTES), "image/jpeg")},
        )

        assert len(filename) == 255
        assert response.status_code == 200
        storage.upload.assert_called_once()

    def test_a_file_one_byte_over_the_photo_limit_gets_the_routes_own_refusal(self, photo_app):
        """
        GIVEN a file one byte over the photo limit, still under the multipart ceiling
        WHEN it is uploaded
        THEN the route answers 400 photo_too_large, not the guard's 413
        """
        app, storage = photo_app

        response = TestClient(app).post(
            _PHOTO_PATH,
            files={"file": ("a.jpg", _photo_file(MAX_FILE_SIZE_BYTES + 1), "image/jpeg")},
        )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "File too large. Maximum size is 5 MB",
            "code": "photo_too_large",
        }
        storage.upload.assert_not_called()


class TestAccessLineMatchesTheResponse:
    """The access line reports the status the client got, and the guard logs with the id."""

    @pytest.mark.parametrize(
        ("kind", "declared", "reason"),
        [
            ("json", False, "streamed_overflow"),
            ("json", True, "declared_content_length"),
            ("multipart", False, "streamed_overflow"),
            ("multipart", True, "declared_content_length"),
        ],
    )
    @pytest.mark.asyncio
    async def test_a_refused_body_is_logged_as_413_under_the_callers_id(
        self, kind, declared, reason
    ):
        """
        GIVEN a body over its cap, JSON or multipart, declared or chunked, with an X-Request-ID
        WHEN the real app refuses it
        THEN the response echoes the id, one access record for that id says 413, and one
            rejection record carries that id and the matching reason
        """
        request_id = f"req-{kind}-{reason}"
        if kind == "json":
            path = "/api/v1/calculate"
            chunks = _json_chunks(DEFAULT_MAX_BODY_BYTES + 2 * _CHUNK)
            content_type = b"application/json"
        else:
            path = _PHOTO_PATH
            chunks = _multipart_chunks(DEFAULT_MAX_MULTIPART_BYTES + 2 * _CHUNK)
            content_type = _MULTIPART_TYPE

        outcome = await _drive(
            create_app(),
            path,
            chunks,
            [(b"content-type", content_type), (b"x-request-id", request_id.encode())],
            declared=declared,
        )

        assert outcome.status == 413
        assert outcome.headers["x-request-id"] == request_id
        access = outcome.access_records(request_id)
        assert [r.status_code for r in access] == [413]  # type: ignore[attr-defined]
        rejected = outcome.rejection_records(request_id)
        assert [r.reason for r in rejected] == [reason]  # type: ignore[attr-defined]


class TestMiddlewareOrder:
    """The logging middleware sits outside the body-size guard."""

    def test_request_logging_is_outside_the_body_size_guard(self):
        """
        GIVEN the full application
        WHEN its middleware stack is read
        THEN RequestLoggingMiddleware wraps BodySizeLimitMiddleware, so the access line
            reports the guard's 413 and the guard's records can carry the request id
        """
        classes = [middleware.cls for middleware in create_app().user_middleware]

        assert classes.index(RequestLoggingMiddleware) < classes.index(BodySizeLimitMiddleware)
