"""Unit tests for the StoredObject streaming handle."""

from io import BytesIO
from unittest.mock import MagicMock

from api.services.storage.stored_object import DEFAULT_CHUNK_SIZE, StoredObject

PAYLOAD = b"0123456789abcdef"


def _stream(data: bytes = PAYLOAD) -> MagicMock:
    """Wrap an in-memory stream in a mock so read/close calls are observable."""
    return MagicMock(wraps=BytesIO(data))


class TestMetadata:
    """Tests for the metadata the handle carries alongside the stream."""

    def test_exposes_content_type_and_length(self):
        """Content type and length are readable without touching the stream."""
        # GIVEN
        stream = _stream()

        # WHEN
        stored = StoredObject(stream, "image/png", len(PAYLOAD))

        # THEN
        assert stored.content_type == "image/png"
        assert stored.content_length == len(PAYLOAD)
        stream.read.assert_not_called()

    def test_content_length_is_none_when_not_reported(self):
        """A backend that omits the size leaves content_length unset."""
        # GIVEN / WHEN
        stored = StoredObject(_stream(), "image/jpeg")

        # THEN
        assert stored.content_length is None

    def test_default_chunk_size_matches_starlette_file_streaming(self):
        """The default chunk is 64 KiB, the same size Starlette uses for files."""
        # THEN
        assert DEFAULT_CHUNK_SIZE == 64 * 1024


class TestChunks:
    """Tests for reading the body in pieces."""

    def test_yields_the_whole_body(self):
        """Concatenated chunks reproduce the stored bytes exactly."""
        # GIVEN
        stored = StoredObject(_stream(), "image/jpeg", len(PAYLOAD))

        # WHEN
        body = b"".join(stored.chunks())

        # THEN
        assert body == PAYLOAD

    def test_reads_in_pieces_rather_than_all_at_once(self):
        """The stream is pulled chunk by chunk, never buffered in one read."""
        # GIVEN a chunk size well below the payload
        stream = _stream()
        stored = StoredObject(stream, "image/jpeg", len(PAYLOAD), chunk_size=4)

        # WHEN
        chunks = list(stored.chunks())

        # THEN four data chunks plus the empty read that ends the loop
        assert chunks == [b"0123", b"4567", b"89ab", b"cdef"]
        assert stream.read.call_count == 5
        assert stream.read.call_args_list[0].args == (4,)

    def test_is_lazy_until_iterated(self):
        """Calling chunks() does not read anything on its own."""
        # GIVEN
        stream = _stream()
        stored = StoredObject(stream, "image/jpeg")

        # WHEN
        stored.chunks()

        # THEN
        stream.read.assert_not_called()

    def test_closes_the_stream_when_exhausted(self):
        """Reading to the end releases the underlying stream."""
        # GIVEN
        stream = _stream()
        stored = StoredObject(stream, "image/jpeg")

        # WHEN
        list(stored.chunks())

        # THEN
        stream.close.assert_called_once()
        assert stored.closed is True

    def test_closes_the_stream_when_abandoned_part_way(self):
        """A partly consumed iterator still releases the stream when dropped.

        This is the client-disconnect case: the response stops mid-download, the
        generator never reaches its end, and the connection must not be stranded.
        """
        # GIVEN
        stream = _stream()
        stored = StoredObject(stream, "image/jpeg", chunk_size=4)
        iterator = stored.chunks()
        next(iterator)
        assert stream.close.call_count == 0

        # WHEN the consumer walks away
        iterator.close()

        # THEN
        stream.close.assert_called_once()
        assert stored.closed is True


class TestClose:
    """Tests for releasing the handle."""

    def test_closes_the_stream_without_reading(self):
        """close() releases an untouched handle."""
        # GIVEN
        stream = _stream()
        stored = StoredObject(stream, "image/jpeg")

        # WHEN
        stored.close()

        # THEN
        stream.close.assert_called_once()
        stream.read.assert_not_called()

    def test_is_idempotent(self):
        """Closing twice touches the stream once.

        The route arms two independent release paths (the generator's finally and a
        background task), so the second one must be harmless.
        """
        # GIVEN
        stream = _stream()
        stored = StoredObject(stream, "image/jpeg")

        # WHEN
        stored.close()
        stored.close()

        # THEN
        stream.close.assert_called_once()

    def test_closes_a_handle_that_was_never_iterated(self):
        """A generator that never started runs no finally, so close() must cover it.

        This is the disconnect-before-the-first-chunk case: nothing else would ever
        release the connection, since abandoning an unstarted generator does not run
        its cleanup.
        """
        # GIVEN
        stream = _stream()
        stored = StoredObject(stream, "image/jpeg")
        stored.chunks()

        # WHEN
        stored.close()

        # THEN
        stream.close.assert_called_once()
