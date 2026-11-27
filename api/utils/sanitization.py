"""Sanitization of user text for input validation: invisible characters and HTML tags.

The result is plain text. Tags are stripped, but ``&``, ``<`` and ``>`` stay as typed instead
of becoming ``&amp;``, ``&lt;`` and ``&gt;``. Nothing renders this text as HTML (React text
nodes, the PDF renderer and the assistant each escape on output), and escaping on the way in
both showed ``R&D`` as ``R&amp;D`` and let the stored value outgrow the field's length cap.
"""

import html

import bleach  # type: ignore[import-untyped]

from api.utils.invisible import strip_invisible

# One pass can expose a tag that the first one hid (``<scr<b>ipt>`` becomes ``ipt>``,
# ``<<b>b>`` becomes ``<b>``). Every pass that changes the text shortens it, so the loop
# ends; the limit only bounds the work on input built to make it long.
_MAX_PASSES = 5


def sanitize_text(value: str, *, max_length: int | None = None) -> str:
    """Remove invisible characters and all HTML tags from text input, keeping plain text.

    The invisible characters go first (control characters, Unicode format characters such as
    bidirectional overrides, zero-width characters and the soft hyphen, variation selectors
    and the other default-ignorable code points, see
    :func:`~api.utils.invisible.strip_invisible`), so that none can hide inside a tag or
    survive it. ``\\n`` and ``\\t`` are kept, and ``\\r\\n`` and a lone ``\\r`` become ``\\n``.

    Tags are stripped with bleach, which escapes ``&``, ``<`` and ``>`` in what it returns.
    Every ``&`` is escaped before bleach runs, so the only entities in its output are the ones
    bleach wrote, and unescaping gives back exactly the characters the user typed: an entity
    typed on purpose (``&lt;``) stays as the text ``&lt;`` and is not decoded. The cleaning
    repeats until the text stops changing, because stripping one tag can leave another
    behind. The result is therefore a fixed point, holds no invisible character and is never
    longer than the input.

    :param value: Raw text input
    :param max_length: Longest result allowed, or None for no limit; a guard that keeps a
        future change in the cleaning from growing the text past the field's cap
    :return: Sanitized plain text without invisible characters and with HTML tags stripped
    :raises ValueError: If the text does not settle within the pass limit, or if the result
        is longer than ``max_length``
    """
    text = strip_invisible(value)
    for _ in range(_MAX_PASSES):
        cleaned = html.unescape(bleach.clean(text.replace("&", "&amp;"), tags=[], strip=True))
        if cleaned == text:
            if max_length is not None and len(cleaned) > max_length:
                msg = "Text is too long after sanitization"
                raise ValueError(msg)
            return cleaned
        text = cleaned
    msg = "Text could not be sanitized"
    raise ValueError(msg)


def sanitize_text_or_none(value: str | None, *, max_length: int | None = None) -> str | None:
    """Sanitize text if not None.

    :param value: Optional raw text input
    :param max_length: Longest result allowed, or None for no limit
    :return: Sanitized text or None
    :raises ValueError: As :func:`sanitize_text`
    """
    if value is None:
        return None
    return sanitize_text(value, max_length=max_length)
