"""Bounded reader for uploaded files.

``await file.read()`` pulls the whole upload into a single ``bytes`` object before
any size check can run, so a multi-gigabyte upload is fully buffered (and its temp
file fully written) before it is rejected. ``read_within_limit`` instead checks the
declared size first and streams the body in bounded chunks, aborting the moment the
cumulative size passes the limit, so an over-large upload never fully buffers.
"""

from typing import Protocol


class UploadTooLarge(Exception):  # noqa: N818 -- domain event, not an *Error
    """Raised when an upload exceeds the permitted size."""


class SupportsAsyncRead(Protocol):
    """Minimal upload interface: a declared size and an async chunked read."""

    size: int | None

    async def read(self, size: int = -1) -> bytes: ...


# Chunk size for streaming reads; large enough to be efficient, small enough that the
# overshoot past the limit before aborting stays negligible.
_CHUNK_SIZE = 64 * 1024


async def read_within_limit(
    file: SupportsAsyncRead, max_bytes: int, *, chunk_size: int = _CHUNK_SIZE
) -> bytes:
    """Read an upload into memory without buffering more than ``max_bytes``.

    The declared ``size`` is rejected up front when it already exceeds the limit; the
    body is then streamed in ``chunk_size`` pieces and the read aborts as soon as the
    accumulated size passes ``max_bytes``, so at most ``max_bytes + chunk_size`` bytes
    are ever held in memory.

    :param file: The upload to read (an ``UploadFile`` or any async chunked reader).
    :param max_bytes: Largest upload accepted, in bytes.
    :param chunk_size: Size of each streamed read, in bytes.
    :return: The full upload content when within the limit.
    :raises UploadTooLarge: When the upload exceeds ``max_bytes``.
    """
    declared = getattr(file, "size", None)
    if declared is not None and declared > max_bytes:
        raise UploadTooLarge

    buffer = bytearray()
    while chunk := await file.read(chunk_size):
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise UploadTooLarge
    return bytes(buffer)
