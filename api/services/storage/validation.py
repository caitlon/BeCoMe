"""Storage-agnostic validation for profile photo uploads."""

from typing import Final

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

# Leading magic bytes used to verify that content matches the declared type.
_IMAGE_SIGNATURES: Final[dict[bytes, str]] = {
    b"\xff\xd8\xff": _MIME_JPEG,
    b"\x89PNG\r\n\x1a\n": _MIME_PNG,
    b"GIF87a": _MIME_GIF,
    b"GIF89a": _MIME_GIF,
    b"RIFF": _MIME_WEBP,  # WebP additionally checks for the WEBP marker
}


def extension_for(content_type: str) -> str:
    """Return the file extension for a validated content type.

    :param content_type: Validated MIME type.
    :return: Lowercase extension without a dot, defaulting to ``jpg``.
    """
    return CONTENT_TYPE_TO_EXTENSION.get(content_type, "jpg")


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
