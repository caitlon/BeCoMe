"""Removal of the wrapper tags from an assistant answer, whole or piece by piece.

The model reads reference text inside the tags of
:data:`~api.assistant.agent.prompt.ASSISTANT_TAGS` and sometimes writes them back into its
answer, where the panel shows them as literal text. Pure text functions, like the ones in
:mod:`api.assistant.agent.checks`: no model calls and no dependency on the rest of the
assistant.

A tag is ``<``, blanks, ``/``, blanks, a name, blanks, ``/``, blanks and ``>``, with each
slash optional and each run of blanks (spaces and tabs) optional. The name is one of the
tag names in any case, with ``-`` and ``_`` alike (``<project-data>``), and the whole tag
lies on one line.
"""

from dataclasses import dataclass

from api.assistant.agent.prompt import ASSISTANT_TAGS

_NAMES = frozenset(name.lower().replace("-", "_") for name in ASSISTANT_TAGS)
_BLANKS = " \t"

# What has been read of the text after a ``<``: the part of the tag it is in, and the name so far.
# Before the name there may be blanks and a slash; the name must be whole before a blank or a
# slash follows it; after it come blanks, a slash and blanks.
_BEFORE, _AFTER_SLASH, _NAME, _BLANKS_AFTER, _SLASH_AFTER = range(5)
_Reading = tuple[int, str]


def _read(reading: _Reading, char: str) -> _Reading | None:
    """Take one more character of the text after a ``<``.

    :param reading: What has been read so far.
    :param char: The next character, neither ``<``, ``>`` nor a line break.
    :return: What has been read with the character, or None when no tag can start this way.
    """
    part, name = reading
    if char in _BLANKS:
        if part != _NAME:
            return reading
        return (_BLANKS_AFTER, name) if name in _NAMES else None
    if char == "/":
        if part == _BEFORE:
            return _AFTER_SLASH, ""
        if part == _BLANKS_AFTER or (part == _NAME and name in _NAMES):
            return _SLASH_AFTER, name
        return None
    if part in (_BEFORE, _AFTER_SLASH, _NAME):
        text = name + ("_" if char == "-" else char.lower())
        if any(known.startswith(text) for known in _NAMES):
            return _NAME, text
    return None


def _is_tag(reading: _Reading) -> bool:
    """Tell whether a ``>`` after what has been read closes a tag."""
    part, name = reading
    return part in (_BLANKS_AFTER, _SLASH_AFTER) or (part == _NAME and name in _NAMES)


def remove_wrapper_tags(text: str) -> str:
    """Remove the wrapper tags, keeping the text between them.

    A tag goes with nothing put in its place, so ``a<docs>, b`` reads ``a, b``. A line that
    held a tag and holds only blanks without it goes whole with its line break (a last line
    with no line break goes with its blanks), so a block between two tags on lines of their
    own leaves no empty lines. Removing a tag can assemble another from the text around
    it, as in ``<do<docs>cs>``; each ``>`` is read against the innermost ``<`` still open
    on its line, as the text reads after the tags inside have gone, so that goes too, and
    removing again changes nothing. Code spans and blocks are not looked at. Only ``\\n``
    ends a line, so the text is expected to have gone through
    :func:`~api.assistant.invisible.strip_invisible`.

    :param text: The text to clean.
    :return: The text without its wrapper tags.
    """
    remover = WrapperTagStreamFilter()
    return remover.feed(text) + remover.finish()


@dataclass
class _Open:
    """A ``<`` that nothing has closed yet on the current line.

    :ivar pos: Where its ``<`` is in the kept text.
    :ivar before: Where the last kept character that is not a blank ended before it.
    :ivar hold: Where the text that it may still take away starts.
    :ivar reading: What follows it, or None when no tag can start this way.
    """

    pos: int
    before: int
    hold: int
    reading: _Reading | None


class WrapperTagStreamFilter:
    """Removes wrapper tags from an answer as its pieces arrive, by the rule of
    :func:`remove_wrapper_tags`.

    The reading carries over from one piece to the next, so the pieces let out joined are
    exactly ``remove_wrapper_tags`` of the whole text, however it was cut, in time that
    grows with its length. Text is held back while a later character may still take it
    away: from the first ``<`` that may still become a tag (one that cannot, because of the
    character after it, lets go at once), and a line that holds nothing but blanks and tags
    so far, because it goes whole when it ends that way. A ``<`` that never closes holds the
    rest of the answer until :meth:`finish`.
    """

    def __init__(self) -> None:
        """Start with no text read and none let out."""
        self._out: list[str] = []  # What is kept and not yet let out.
        self._base = 0  # How many characters were let out.
        self._line_start = 0  # Where the current line starts in the kept text.
        self._text_end = 0  # Just past the last kept character of the line that is no blank.
        self._tagged = False  # Whether a tag was removed from the current line.
        self._open: list[_Open] = []  # The unclosed ``<`` of the line, outermost first.
        self._live = 0  # The first of them that a tag may still start at.

    def feed(self, piece: str) -> str:
        """Take the next piece of the answer.

        :param piece: The text that arrived.
        :return: The text that can now be shown, empty while it is held back.
        """
        for char in piece:
            self._place(char)
        return self._take(self._held() - self._base)

    def finish(self) -> str:
        """Release what is still held back, once the whole answer has been fed.

        :return: The rest of the answer without wrapper tags.
        """
        if self._tagged and self._text_end == self._line_start:
            del self._out[self._line_start - self._base :]
        return self._take(len(self._out))

    def _held(self) -> int:
        """Return where the text that may still change starts."""
        if self._live < len(self._open):
            return self._open[self._live].hold
        if self._text_end == self._line_start:
            return self._line_start
        return self._base + len(self._out)

    def _take(self, count: int) -> str:
        """Let out the first ``count`` kept characters."""
        text = "".join(self._out[:count])
        del self._out[:count]
        self._base += count
        return text

    def _place(self, char: str) -> None:
        """Keep a character, or open or close a tag, or end the line."""
        if char == "\n":
            self._end_line()
        elif char == "<":
            self._push()
        elif char == ">":
            self._close()
        else:
            self._append(char)
            self._advance(char)

    def _append(self, char: str) -> None:
        """Keep a character."""
        self._out.append(char)
        if char not in _BLANKS:
            self._text_end = self._base + len(self._out)

    def _push(self) -> None:
        """Keep a ``<`` and wait for what follows it."""
        pos = self._base + len(self._out)
        blank_so_far = self._text_end == self._line_start
        self._open.append(
            _Open(pos, self._text_end, self._line_start if blank_so_far else pos, (_BEFORE, ""))
        )
        self._append("<")

    def _advance(self, char: str) -> None:
        """Let the innermost open ``<`` read a kept character."""
        if not self._open:
            return
        top = self._open[-1]
        if top.reading is None:
            return
        top.reading = _read(top.reading, char)
        if top.reading is None and self._live == len(self._open) - 1:
            self._live = len(self._open)

    def _close(self) -> None:
        """Remove the tag that a ``>`` closes, or keep the ``>`` when none."""
        if self._open and (top := self._open[-1]).reading is not None and _is_tag(top.reading):
            del self._out[top.pos - self._base :]
            self._text_end = top.before
            self._open.pop()
            self._live = min(self._live, len(self._open))
            self._tagged = True
            return
        # The ``>`` stays in the text, so no ``<`` before it can close a tag any more.
        self._append(">")
        self._open.clear()
        self._live = 0

    def _end_line(self) -> None:
        """End the line, dropping it when it held tags and nothing else."""
        if self._tagged and self._text_end == self._line_start:
            del self._out[self._line_start - self._base :]
        else:
            self._append("\n")
        self._line_start = self._text_end = self._base + len(self._out)
        self._tagged = False
        self._open.clear()
        self._live = 0
