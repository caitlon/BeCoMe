"""Tests for the bounded upload reader."""

import asyncio
from io import BytesIO

import pytest
from api.utils.upload import UploadTooLarge, read_within_limit
from starlette.datastructures import UploadFile


def _upload(data: bytes) -> UploadFile:
    """Wrap raw bytes in a Starlette UploadFile with a known declared size."""
    return UploadFile(file=BytesIO(data), size=len(data), filename="photo.jpg")


class _CountingReader:
    """Async reader with no declared size that records how many bytes it served."""

    size = None

    def __init__(self, total: int) -> None:
        self._remaining = total
        self.served = 0

    async def read(self, size: int = -1) -> bytes:
        give = self._remaining if size < 0 else min(size, self._remaining)
        self._remaining -= give
        self.served += give
        return b"x" * give


class TestReadWithinLimit:
    """read_within_limit buffers a bounded amount and rejects oversized uploads."""

    def test_returns_content_within_the_limit(self):
        """GIVEN a small upload WHEN read THEN its bytes are returned intact."""
        data = b"hello world"
        assert asyncio.run(read_within_limit(_upload(data), max_bytes=100)) == data

    def test_rejects_by_declared_size_without_reading(self):
        """GIVEN an upload whose declared size exceeds the limit THEN it is rejected."""
        with pytest.raises(UploadTooLarge):
            asyncio.run(read_within_limit(_upload(b"x" * 200), max_bytes=100))

    def test_rejects_while_streaming_when_size_unknown(self):
        """GIVEN a body over the limit with no declared size THEN streaming still rejects it."""
        with pytest.raises(UploadTooLarge):
            asyncio.run(read_within_limit(_CountingReader(200), max_bytes=100, chunk_size=32))

    def test_stops_reading_once_over_the_limit(self):
        """GIVEN a huge body with no declared size THEN it aborts without buffering all of it."""
        reader = _CountingReader(10 * 1024 * 1024)
        with pytest.raises(UploadTooLarge):
            asyncio.run(read_within_limit(reader, max_bytes=100, chunk_size=32))
        assert reader.served <= 100 + 32
