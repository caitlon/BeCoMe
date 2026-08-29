"""Storage-agnostic validation for profile photo uploads."""

import logging
from io import BytesIO
from typing import Final

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger("api.service.storage")

_MIME_JPEG: Final = "image/jpeg"
_MIME_PNG: Final = "image/png"
_MIME_GIF: Final = "image/gif"
_MIME_WEBP: Final = "image/webp"

# Trusted content type to extension map (never derived from the client filename).
CONTENT_TYPE_TO_EXTENSION: Final[dict[str, str]] = {
    _MIME_JPEG: "jpg",
    _MIME_PNG: "png",
    _MIME_GIF: "gif",
    _MIME_WEBP: "webp",
}
ALLOWED_CONTENT_TYPES: Final = frozenset(CONTENT_TYPE_TO_EXTENSION)
MAX_FILE_SIZE_BYTES: Final = 5 * 1024 * 1024  # 5 MB

# Pixel budget for an avatar. The byte cap above does not bound this: image formats
# compress uniform areas so well that a few hundred KB can describe tens of gigapixels,
# which is a decompression bomb, and the memory is spent the moment anything decodes it.
# 4096x4096 is far more than an avatar ever needs while accepting real camera photos.
MAX_IMAGE_PIXELS: Final = 4096 * 4096
MAX_IMAGE_DIMENSION: Final = 8192

# Leading magic bytes used to verify that content matches the declared type.
_IMAGE_SIGNATURES: Final[dict[bytes, str]] = {
    b"\xff\xd8\xff": _MIME_JPEG,
    b"\x89PNG\r\n\x1a\n": _MIME_PNG,
    b"GIF87a": _MIME_GIF,
    b"GIF89a": _MIME_GIF,
    b"RIFF": _MIME_WEBP,  # WebP also checks for the WEBP marker
}


def extension_for(content_type: str) -> str:
    """Return the file extension for a validated content type.

    :param content_type: Validated MIME type.
    :return: Lowercase extension without a dot, defaulting to ``jpg``.
    """
    return CONTENT_TYPE_TO_EXTENSION.get(content_type, "jpg")


def validate_image_dimensions(content: bytes) -> bool:
    """Check that an image's pixel dimensions stay within the avatar budget.

    Only the header is parsed. ``Image.open`` is lazy, so the pixel data is never
    decoded and a bomb costs nothing to reject. This is the check the byte cap cannot
    do: a highly compressible image well under 5 MB can declare a canvas of tens of
    gigapixels, and whatever decodes it later pays that in memory.

    Pillow's own :class:`~PIL.Image.DecompressionBombError` is caught as well, since it
    fires from ``open`` once a canvas exceeds twice its internal limit.

    :param content: Raw file bytes.
    :return: True when the image parses and fits both the per-side and total budgets.
    """
    try:
        with Image.open(BytesIO(content)) as image:
            width, height = image.size
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        return False

    if width < 1 or height < 1:
        return False
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        logger.info(
            "Rejected oversized image upload",
            extra={"event": "upload_dimensions_rejected", "width": width, "height": height},
        )
        return False
    if width * height > MAX_IMAGE_PIXELS:
        logger.info(
            "Rejected oversized image upload",
            extra={"event": "upload_dimensions_rejected", "width": width, "height": height},
        )
        return False
    return True


def validate_image_content(content: bytes, claimed_content_type: str) -> bool:
    """Check that raw bytes match the declared image content type.

    The leading magic bytes are inspected so a renamed or spoofed file is
    rejected before it reaches storage.

    :param content: Raw file bytes.
    :param claimed_content_type: Content type declared by the client.
    :return: True when the signature matches the declared type.
    """
    if not content:
        return False

    for signature, actual_type in _IMAGE_SIGNATURES.items():
        if content.startswith(signature):
            # WebP carries a RIFF header followed by a WEBP marker at bytes 8-12.
            if signature == b"RIFF":
                if len(content) >= 12 and content[8:12] == b"WEBP":
                    return claimed_content_type == _MIME_WEBP
                continue
            return claimed_content_type == actual_type

    return False
