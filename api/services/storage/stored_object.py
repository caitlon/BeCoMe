"""Open handle over a stored object, read in chunks instead of all at once."""

from collections.abc import Iterator
from typing import Protocol

#: Bytes pulled from the backend per iteration. Matches Starlette's own file
#: streaming, which is tuned for the same trade-off between syscalls and memory.
DEFAULT_CHUNK_SIZE = 64 * 1024


class ByteStream(Protocol):
    """Readable, closable byte source backing a stored object.

    Narrow on purpose: an S3 ``StreamingBody``, a local file, and a ``BytesIO``
    all satisfy it, so the storage layer never has to name a vendor type.
    """

    def read(self, size: int, /) -> bytes:
        """Return up to ``size`` bytes from the current position.

        :param size: Maximum number of bytes to return.
        :return: The bytes read; empty once the stream is exhausted.
        """

    def close(self) -> None:
        """Release the underlying connection or file handle."""


class StoredObject:
    """An object opened for reading, whose body is still on the wire.

    Holding the stream rather than its bytes is the point: the storage backend
    answers with headers first, so a response can start immediately and the body
    is pulled only as it is written out. Nothing is buffered in the process.

    The handle owns a live connection and therefore has a lifecycle: it stays open until
    :meth:`chunks` runs to the end or :meth:`close` is called. Leaving it open
    leaks a connection from the backend pool.

    :param stream: Open byte stream positioned at the start of the object.
    :param content_type: MIME type reported by the backend.
    :param content_length: Object size in bytes, when the backend reports one.
    :param chunk_size: Bytes to pull from the stream per iteration.
    """

    def __init__(
        self,
        stream: ByteStream,
        content_type: str,
        content_length: int | None = None,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        """Wrap an open stream together with the metadata needed to serve it."""
        self._stream = stream
        self._content_type = content_type
        self._content_length = content_length
        self._chunk_size = chunk_size
        self._closed = False

    @property
    def content_type(self) -> str:
        """MIME type reported by the storage backend."""
        return self._content_type

    @property
    def content_length(self) -> int | None:
        """Object size in bytes, or None when the backend did not report one."""
        return self._content_length

    @property
    def closed(self) -> bool:
        """Whether the underlying stream has been released."""
        return self._closed

    def chunks(self) -> Iterator[bytes]:
        """Yield the body in chunks, releasing the stream when iteration ends.

        The ``finally`` covers abandonment as well as exhaustion: a consumer that
        stops part way leaves the generator unfinished, and closing it still frees
        the connection instead of stranding it.

        :return: Iterator over the object bytes.
        """
        try:
            while chunk := self._stream.read(self._chunk_size):
                yield chunk
        finally:
            self.close()

    def close(self) -> None:
        """Release the underlying stream. Calling it again does nothing."""
        if self._closed:
            return
        self._closed = True
        self._stream.close()
