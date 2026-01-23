"""HTML sanitization utilities for input validation."""

import bleach  # type: ignore[import-untyped]


def sanitize_text(value: str) -> str:
    """Remove all HTML tags from text input.

    :param value: Raw text input
    :return: Sanitized text with HTML tags stripped
    """
    result: str = bleach.clean(value, tags=[], strip=True)
    return result


def sanitize_text_or_none(value: str | None) -> str | None:
    """Sanitize text if not None.

    :param value: Optional raw text input
    :return: Sanitized text or None
    """
    if value is None:
        return None
    return sanitize_text(value)
