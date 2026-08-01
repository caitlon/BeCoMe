"""Unit tests for StoredObjectResponse."""

from io import BytesIO
from unittest.mock import MagicMock

import anyio
import pytest
from starlette.requests import ClientDisconnect

from api.services.storage.stored_object import StoredObject
from api.utils.streaming import StoredObjectResponse

PAYLOAD = b"0123456789abcdef"
CHUNK_SIZE = 4
TOTAL_CHUNKS = len(PAYLOAD) // CHUNK_SIZE


def _stored(content_length: int | None = len(PAYLOAD)) -> tuple[StoredObject, MagicMock]:
    """Build a chunked handle plus the mock stream behind it."""
    stream = MagicMock(wraps=BytesIO(PAYLOAD))
    return StoredObject(stream, "image/png", content_length, chunk_size=CHUNK_SIZE), stream


def _scope(spec_version: str) -> dict[str, object]:
    """Build a minimal HTTP scope pinned to one ASGI spec version.

    The version decides how Starlette reacts to a client that goes away, and the
    two branches behave differently enough that both are worth exercising.
    """
    return {"type": "http", "asgi": {"version": "3.0", "spec_version": spec_version}}


class _Recorder:
    """Collect the ASGI messages a response sends."""

    def __init__(self, disconnect: bool = False, fail_after: int | None = None) -> None:
        self._disconnect = disconnect
        self._fail_after = fail_after
        self._client_left = anyio.Event()
        self.headers: dict[bytes, bytes] = {}
        self.body = b""
        self.chunks = 0

    async def receive(self) -> dict[str, str]:
        """Report a disconnect once the first chunk is out, or block forever."""
        if not self._disconnect:
            await anyio.sleep(3600)
        await self._client_left.wait()
        return {"type": "http.disconnect"}

    async def send(self, message: dict) -> None:
        """Record one outgoing message, simulating a dropped client if asked."""
        if message["type"] == "http.response.start":
            self.headers = dict(message["headers"])
        if message["type"] == "http.response.body" and message.get("body"):
            self.chunks += 1
            self.body += message["body"]
            if self._disconnect:
                self._client_left.set()
                await anyio.sleep(0.05)
            if self._fail_after is not None and self.chunks >= self._fail_after:
                raise OSError("client went away")


class TestHeaders:
    """Tests for the headers the response declares."""

    @pytest.mark.asyncio
    async def test_declares_content_length_and_type(self):
        """The reported size and media type reach the wire."""
        # GIVEN
        stored, _ = _stored()
        recorder = _Recorder()

        # WHEN
        await StoredObjectResponse(stored)(_scope("2.3"), recorder.receive, recorder.send)

        # THEN
        assert recorder.headers[b"content-length"] == str(len(PAYLOAD)).encode()
        assert recorder.headers[b"content-type"] == b"image/png"
        assert recorder.body == PAYLOAD

    @pytest.mark.asyncio
    async def test_omits_content_length_when_the_backend_did_not_report_one(self):
        """Without a known size the response falls back to chunked transfer."""
        # GIVEN
        stored, _ = _stored(content_length=None)
        recorder = _Recorder()

        # WHEN
        await StoredObjectResponse(stored)(_scope("2.3"), recorder.receive, recorder.send)

        # THEN
        assert b"content-length" not in recorder.headers
        assert recorder.body == PAYLOAD

    @pytest.mark.asyncio
    async def test_keeps_the_caller_supplied_headers(self):
        """Caching directives passed by the route survive."""
        # GIVEN
        stored, _ = _stored()
        recorder = _Recorder()
        response = StoredObjectResponse(stored, headers={"Cache-Control": "public, immutable"})

        # WHEN
        await response(_scope("2.3"), recorder.receive, recorder.send)

        # THEN
        assert recorder.headers[b"cache-control"] == b"public, immutable"


class TestRelease:
    """Tests that the bucket connection is never left open.

    Starlette handles a vanished client in two ways depending on the ASGI spec
    version the server advertises: the older branch delivers an ``http.disconnect``
    message and returns normally, the newer one lets the failed write surface as an
    exception. Both must end with the handle released.
    """

    @pytest.mark.asyncio
    async def test_closes_after_a_complete_response(self):
        """A fully written response releases the handle exactly once."""
        # GIVEN
        stored, stream = _stored()
        recorder = _Recorder()

        # WHEN
        await StoredObjectResponse(stored)(_scope("2.3"), recorder.receive, recorder.send)

        # THEN
        assert recorder.chunks == TOTAL_CHUNKS
        assert stored.closed is True
        stream.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_closes_when_the_client_sends_a_disconnect(self):
        """A disconnect message part way through still releases the handle."""
        # GIVEN
        stored, stream = _stored()
        recorder = _Recorder(disconnect=True)

        # WHEN
        await StoredObjectResponse(stored)(_scope("2.3"), recorder.receive, recorder.send)

        # THEN the transfer stopped early and nothing stayed open
        assert recorder.chunks < TOTAL_CHUNKS
        assert stored.closed is True
        stream.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_closes_when_writing_to_the_client_fails(self):
        """A write that fails mid-stream releases the handle before propagating.

        On this branch Starlette abandons the body iterator instead of running any
        cleanup hook, so without the wrapper the connection would sit in limbo until
        an async generator that may never be collected finally is.
        """
        # GIVEN
        stored, stream = _stored()
        recorder = _Recorder(fail_after=2)

        # WHEN
        with pytest.raises(ClientDisconnect):
            await StoredObjectResponse(stored)(_scope("2.4"), recorder.receive, recorder.send)

        # THEN
        assert recorder.chunks == 2
        assert stored.closed is True
        stream.close.assert_called_once()
