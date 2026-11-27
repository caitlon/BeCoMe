"""Sanitization of user text for input validation: invisible characters and HTML tags."""

import bleach  # type: ignore[import-untyped]

from api.utils.invisible import strip_invisible


def sanitize_text(value: str) -> str:
    """Remove invisible characters and all HTML tags from text input.

    The invisible characters go first (control characters, Unicode format characters such as
    bidirectional overrides, zero-width characters and the soft hyphen, variation selectors
    and the other default-ignorable code points, see
    :func:`~api.utils.invisible.strip_invisible`), so that none can hide inside a tag or
    survive it. ``\\n`` and ``\\t`` are kept, and ``\\r\\n`` and a lone ``\\r`` become ``\\n``.

    :param value: Raw text input
    :return: Sanitized text without invisible characters and with HTML tags stripped
    """
    result: str = bleach.clean(strip_invisible(value), tags=[], strip=True)
    return result


def sanitize_text_or_none(value: str | None) -> str | None:
    """Sanitize text if not None.

    :param value: Optional raw text input
    :return: Sanitized text or None
    """
    if value is None:
        return None
    return sanitize_text(value)
