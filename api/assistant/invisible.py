"""Removal of the characters that render as nothing, from every text the assistant handles.

Some characters draw no glyph or change how the text around them is drawn: control
characters, the formatting characters of Unicode category Cf (zero-width spaces and joiners,
the soft hyphen, bidirectional overrides and isolates, the byte order mark, the tag
characters), the variation selectors, the combining grapheme joiner and the Hangul fillers.
A reader does not see them, but the model and the number check do, so they can hide text
from the reader (a right-to-left override makes ``14.19`` display as ``91.41``), or split
a number so that its parts ground on their own (``2``, a zero-width space and ``3`` read as
two numbers, not as 23). They are removed from the answer, from what the model reads and
from the user's own input.

The joiners that bind an emoji sequence (U+200D) are removed too, so a family or a flag
sequence shows as its separate emoji. That is accepted: the loss is cosmetic, and keeping
the joiner would keep a character that can split a number.
"""

import unicodedata

# What stays of the control characters: the line break and the tab.
_KEPT_CONTROLS = "\n\t"

# Not Cc or Cf, yet drawn as nothing: the combining grapheme joiner, the Hangul fillers and
# the variation selectors (the Mongolian ones, the standard ones and the supplementary ones).
_EXTRA_INVISIBLE = (
    0x034F,
    0x115F,
    0x1160,
    0x3164,
    0xFFA0,
    0x180B,
    0x180C,
    0x180D,
    0x180F,
    *range(0xFE00, 0xFE10),
    *range(0xE0100, 0xE01F0),
)

# The fixed part of the work, for ``str.translate``: a control character that Python calls
# whitespace becomes a space, so the words on both sides do not run together; any other
# control character and every extra goes. The carriage return is already a line break when
# the table is applied.
_TABLE: dict[int, str | None] = {
    **{
        code: " " if chr(code).isspace() else None
        for code in (*range(0x20), *range(0x7F, 0xA0))
        if chr(code) not in _KEPT_CONTROLS
    },
    **dict.fromkeys(_EXTRA_INVISIBLE),
}


def strip_invisible(text: str) -> str:
    """Remove the characters of a text that render as nothing.

    ``\\r\\n`` and a lone ``\\r`` become ``\\n``; ``\\n`` and ``\\t`` stay. Any other control
    character that Python calls whitespace (the vertical tab, the form feed, the separators
    U+001C to U+001F and U+0085) becomes a space. Every other control character and every
    character of Unicode category Cf is removed, and so are the combining grapheme joiner,
    the Hangul fillers and the variation selectors. Visible text, accented letters and
    emoji included, is unchanged.

    :param text: The text to clean.
    :return: The text without invisible characters.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").translate(_TABLE)
    if text.isascii():
        return text
    return "".join(char for char in text if char.isascii() or unicodedata.category(char) != "Cf")
