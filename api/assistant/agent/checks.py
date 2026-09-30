"""Post-generation checks on an assistant answer: its citations and its numbers.

Pure text functions: no model calls, no retries, and no dependency on the rest of the
assistant, so an offline evaluation script can use them as they are.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Context, Decimal

# A bracket group: square brackets, or the full-width lenticular ones some models emit.
_BRACKET = re.compile(r"\[([^\[\]]*)\]|\u3010([^\u3010\u3011]*)\u3011")

# What a citation looks like inside a bracket: an optional label word (letters of any
# script, then an optional space, dot, colon, hash or numero sign) and then integers of
# one to three digits separated by commas, semicolons, spaces, hyphens or en dashes.
_CITATION_CONTENT = re.compile(
    r"\s*(?:[^\W\d_]+[\s.:#\u2116]*)?(?P<ints>[0-9]{1,3}(?:[,;\s\-\u2013]+[0-9]{1,3})*)\s*"
)
_CITED_RANGE = re.compile(r"([0-9]{1,3})(?:\s*[-\u2013]\s*([0-9]{1,3}))?")

# What is dropped from an answer before its numbers are scanned.
_LINK_TARGET = re.compile(r"\]\((?:https?://|/|#)[^)\s]*\)")
_BARE_URL = re.compile(r"https?://\S+")
_LIST_NUMBERING = re.compile(r"^[ \t]*[0-9]+[.)]\s", re.MULTILINE)

_SPACE = "[ \u00a0\u202f]"
# The four forms of a number, tried in this order at each position.
_NUMBER = re.compile(
    rf"(?P<spaced>[0-9]{{1,3}}(?:{_SPACE}[0-9]{{3}})+(?![0-9])(?:,[0-9]+)?)"
    r"|(?P<grouped>[0-9]{1,3}(?:,[0-9]{3})+\.[0-9]+)"
    r"|(?P<commas>[0-9]+(?:,[0-9]+)+)"
    r"|(?P<plain>[0-9]+(?:\.[0-9]+)?)"
)
_LETTER_OR_UNDERSCORE = re.compile(r"[^\W\d]")
_MINUS_SIGNS = "-\u2212"
_OPENING_BRACKETS = "([{"


def _cited_numbers(content: str) -> set[int] | None:
    """Read the integers a bracket names, if the bracket is citation-like.

    :param content: The text between the brackets.
    :return: The named integers, ranges expanded, or None when the bracket is not a
        citation (a decimal, four digits, words).
    """
    match = _CITATION_CONTENT.fullmatch(content)
    if match is None:
        return None
    numbers: set[int] = set()
    for found in _CITED_RANGE.finditer(match["ints"]):
        first = int(found[1])
        last = int(found[2]) if found[2] is not None else first
        numbers.update(range(first, last + 1) if first <= last else (first, last))
    return numbers


def _citation_spans(text: str) -> list[tuple[int, int, set[int]]]:
    """Find every citation-like bracket group in a text.

    :param text: The text to scan.
    :return: A ``(start, end, numbers)`` triple per citation-like group, in order.
    """
    spans: list[tuple[int, int, set[int]]] = []
    for group in _BRACKET.finditer(text):
        numbers = _cited_numbers(group[1] if group[1] is not None else group[2])
        if numbers is not None:
            spans.append((group.start(), group.end(), numbers))
    return spans


def check_citations(answer: str, valid_numbers: set[int]) -> bool:
    """Check that every citation in the answer names a source that was given.

    A citation is a bracket group such as ``[1]``, ``[1, 2]``, ``[1-3]``,
    ``[Source 1]``, ``[doc1]`` or the full-width ``\u30101\u3011``; a range names every
    number in it, and a markdown link ``[1](https://...)`` counts as the citation
    ``[1]``. A bracket holding a decimal, such as ``[11.54, 14.19]``, is not a citation.
    Known limit: a square-bracketed group of bare integers is read as a citation, so a
    fuzzy number written ``[6, 8, 11]`` is misread.

    :param answer: The model's final answer text.
    :param valid_numbers: The source numbers handed out this turn, one-based.
    :return: True when every cited number is in ``valid_numbers``; an answer with no
        citation passes, and a citation of ``0`` never does.
    """
    cited: set[int] = set()
    for _start, _end, numbers in _citation_spans(answer):
        cited |= numbers
    return cited <= valid_numbers


@dataclass(frozen=True)
class _Token:
    """One number as written in a text, with every way of reading it.

    :ivar written: The token as it appears in the text, sign included.
    :ivar readings: Each reading is the list of numbers the token stands for; the token
        is grounded when all numbers of any one reading are.
    """

    written: str
    readings: list[list[Decimal]]


def _readings(form: str, text: str, negative: bool) -> list[list[Decimal]]:
    """List the ways a matched number can be read.

    :param form: Which form matched: ``spaced``, ``grouped``, ``commas`` or ``plain``.
    :param text: The matched text, without a sign.
    :param negative: Whether the number carries a minus sign.
    :return: The readings, each a list of numbers.
    """
    if form == "spaced":
        readings = [[Decimal(re.sub(_SPACE, "", text).replace(",", "."))]]
    elif form == "grouped":
        readings = [[Decimal(text.replace(",", ""))]]
    elif form == "commas":
        parts = text.split(",")
        readings = [[Decimal(part) for part in parts]]
        if len(parts) == 2:
            readings.append([Decimal(f"{parts[0]}.{parts[1]}")])
        if len(parts[0]) <= 3 and all(len(part) == 3 for part in parts[1:]):
            readings.append([Decimal("".join(parts))])
    else:
        readings = [[Decimal(text)]]
    if negative:
        readings = [[-reading[0], *reading[1:]] for reading in readings]
    return readings


def _has_minus_sign(text: str, start: int) -> bool:
    """Tell whether a minus directly before a number is its sign.

    It is when it opens the text or follows whitespace or an opening bracket; in
    ``20-40`` it is a range.

    :param text: The scanned text.
    :param start: Index of the number's first digit.
    :return: True when the character before the digit is a sign.
    """
    if start == 0 or text[start - 1] not in _MINUS_SIGNS:
        return False
    return start == 1 or text[start - 2].isspace() or text[start - 2] in _OPENING_BRACKETS


def _scan_numbers(text: str) -> list[_Token]:
    """Find the numbers in a text.

    A token next to a letter or an underscore (``Qwen3``, ``1st``, ``H2O``) is not a
    number.

    :param text: The text to scan.
    :return: The number tokens, in reading order.
    """
    tokens: list[_Token] = []
    for match in _NUMBER.finditer(text):
        start, end = match.span()
        if start > 0 and _LETTER_OR_UNDERSCORE.match(text[start - 1]):
            continue
        if end < len(text) and _LETTER_OR_UNDERSCORE.match(text[end]):
            continue
        negative = _has_minus_sign(text, start)
        form = str(match.lastgroup)
        tokens.append(
            _Token(
                written=text[start - 1 : end] if negative else match[0],
                readings=_readings(form, match[0], negative),
            )
        )
    return tokens


def _strip_answer(answer: str) -> str:
    """Remove what is not a data point from an answer: links, URLs, numbering, citations.

    :param answer: The model's final answer text.
    :return: The text with the link targets, bare URLs, list numbering and citation-like
        brackets removed.
    """
    text = _LINK_TARGET.sub("]", answer)
    text = _BARE_URL.sub(" ", text)
    text = _LIST_NUMBERING.sub("", text)
    pieces: list[str] = []
    position = 0
    for start, end, _numbers in _citation_spans(text):
        pieces.append(text[position:start])
        pieces.append(" ")
        position = end
    pieces.append(text[position:])
    return "".join(pieces)


def _places(number: Decimal) -> int:
    """Count the decimals a number was written with.

    :param number: A number read from a text.
    :return: How many digits follow the decimal point, ``0`` for an integer.
    """
    exponent = number.as_tuple().exponent
    return max(0, -exponent) if isinstance(exponent, int) else 0


def _quantized(value: Decimal, places: int, rounding: str) -> Decimal:
    """Round a value to a number of decimals without any loss of digits.

    :param value: The value to round.
    :param places: How many decimals to keep.
    :param rounding: A :mod:`decimal` rounding mode.
    :return: The rounded value.
    """
    context = Context(prec=len(value.as_tuple().digits) + places + 2, rounding=rounding)
    return value.quantize(Decimal(1).scaleb(-places), context=context)


class _Grounding:
    """The values a text collection states, and what a written number may round from."""

    def __init__(self, texts: Iterable[str]) -> None:
        """Read every number of every reading of every token in the texts.

        :param texts: The grounding texts, scanned as they are.
        """
        self._values = {
            number
            for text in texts
            for token in _scan_numbers(text)
            for reading in token.readings
            for number in reading
        }
        self._by_places: dict[int, set[Decimal]] = {}

    def covers(self, number: Decimal) -> bool:
        """Tell whether some grounding value rounds or truncates to the number.

        :param number: A number from the answer; the decimals it was written with
            decide how coarsely the grounding values are compared.
        :return: True when a value, quantized to those decimals, equals the number
            under round-half-up or under truncation.
        """
        places = _places(number)
        if places not in self._by_places:
            self._by_places[places] = {
                _quantized(value, places, rounding)
                for value in self._values
                for rounding in (ROUND_HALF_UP, ROUND_DOWN)
            }
        return number in self._by_places[places]


def find_ungrounded_numbers(answer: str, grounding_texts: list[str]) -> list[str]:
    """Return the numbers in the answer that no grounding text supports.

    Before scanning, the answer loses the target of markdown links, bare URLs, list
    numbering at the start of a line and citation-like brackets (see
    :func:`check_citations`). A number is then a digit run, with a sign when a minus
    opens the text or follows whitespace or an opening bracket, and never one that sits
    next to a letter or an underscore. Thousands may be grouped with spaces
    (``1 000``) or commas (``1,234.56``), and a comma between digit groups is read every
    way it can be: ``14,19`` as the decimal 14.19 or as 14 and 19, ``1,234`` as 1234 or
    as 1 and 234, ``6,8,11`` as three numbers. A token is grounded when one of its
    readings has all its numbers grounded.

    A number written with ``d`` decimals is grounded when some number in the grounding
    texts, quantized to ``d`` decimals, equals it under round-half-up or under
    truncation: the data says ``14.1923076923``, so ``14.19``, ``14.2`` and ``14`` are
    grounded and ``15`` is not. Percentages are compared as written: ``0.2`` does not
    ground ``20 %``. Known limit: a square-bracketed group of bare integers is read as
    a citation and skipped, so a fuzzy number written ``[6, 8, 11]`` is not checked.

    :param answer: The model's final answer text.
    :param grounding_texts: Everything the answer may legitimately quote: the source
        registry's chunk texts, the tool outputs, the rendered project block, the
        user's question and the user's own earlier turns, and the pinned numbers. Never
        the system prompt, whose citation example would ground a digit.
    :return: Each ungrounded number as written in the answer, sign included, once, in
        order of first appearance.
    """
    grounding = _Grounding(grounding_texts)
    ungrounded: list[str] = []
    for token in _scan_numbers(_strip_answer(answer)):
        if token.written in ungrounded:
            continue
        if not any(
            all(grounding.covers(number) for number in reading) for reading in token.readings
        ):
            ungrounded.append(token.written)
    return ungrounded
