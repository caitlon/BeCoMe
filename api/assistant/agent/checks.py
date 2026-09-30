"""Post-generation checks on an assistant answer: its citations and its numbers.

Pure text functions: no model calls, no retries, and no dependency on the rest of the
assistant, so an offline evaluation script can use them as they are.
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Context, Decimal

# A bracket group: square brackets, or the full-width lenticular ones some models emit.
_BRACKET = re.compile(r"\[([^\[\]]*)\]|\u3010([^\u3010\u3011]*)\u3011")

# The words that may label a citation, in any case: source, document, reference,
# excerpt and passage in English and Czech, and source in Russian, each with the short
# endings that make its plural and its cases. The whole word must match, so a longer
# word that only begins like one (``[reflection 3]``, ``[docker 3]``,
# ``[document-like 3]``) does not label a citation, and neither does any other word
# before a number (``[lower 6, upper 11]``, ``[Q1-Q3]``): the bracket is ordinary text.
_LABEL_WORDS = (
    r"sources?",
    r"src",
    r"docs?",
    r"documents?",
    r"refs?",
    r"references?",
    r"excerpts?",
    r"passages?",
    r"zdroj(?:e|u|y|\u016f|\u016fm|ech)?",
    r"dokument(?:y|u|\u016f)?",
    r"\u00faryv(?:ek|ky|ku|k\u016f)",
    r"pas\u00e1\u017e(?:e|\u00ed)?",
    r"\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a"
    r"(?:\u0430|\u0443|\u043e\u043c|\u0435|\u0438|\u043e\u0432|"
    r"\u0430\u043c|\u0430\u043c\u0438|\u0430\u0445)?",
)

# What a citation looks like inside a bracket: integers of one to three digits separated
# by commas, semicolons, spaces, hyphens or en dashes, each with an optional label word
# in front (then an optional space, dot, colon, hash or numero sign).
_LABEL = "(?:" + "|".join(_LABEL_WORDS) + r")[\s.:#\u2116]*"
_CITATION_ITEM = rf"(?:{_LABEL})?\d{{1,3}}"
_CITATION_CONTENT = re.compile(
    rf"\s*{_CITATION_ITEM}(?:[,;\s\-\u2013]+{_CITATION_ITEM})*\s*", re.IGNORECASE
)
_LABEL_WORD = re.compile(_LABEL, re.IGNORECASE)
_CITED_RANGE = re.compile(r"(\d{1,3})(?:\s*[-\u2013]\s*(\d{1,3}))?")

# What is dropped from an answer before its numbers are scanned. A link's target stops
# at the first bracket, parenthesis or space, so that a text made of unclosed "](" never
# makes the scan run to the end of the text once per bracket.
_LINK_TARGET = re.compile(r"\]\([^()\[\]\s]+\)")
_BARE_URL = re.compile(r"https?://\S+")
_DATE_ISO = re.compile(r"(?<![\w.])\d{4}-\d{2}-\d{2}(?!\d)")
_DATE_DOTTED = re.compile(r"(?<![\w.])\d{1,2}\. ?\d{1,2}\. ?\d{4}(?!\d)")
# A word, its hyphen-joined digit run, and its dot- or comma-joined digit tail (v1.2.3,
# Qwen3,5, COVID-19.5). Whether the word holds a digit and a letter, or is a capitalised
# name before a hyphen and digits, is decided in _drop_words. A word never starts right
# after a number or a dot (84.3W-1, x.y6_1), so a name is not cut out of a number glued
# to it. A hyphen-joined digit run is left out when a word character follows it
# (870-14cm.104), so that the mixed word 14cm.104 is found whole.
_WORD = re.compile(_LABEL, re.IGNORECASE)
_CITED_RANGE = re.compile(r"(\d{1,3})(?:\s*[-\u2013]\s*(\d{1,3}))?")

# What is dropped from an answer before its numbers are scanned. A link's target stops
# at the first bracket, parenthesis or space, so that a text made of unclosed "](" never
# makes the scan run to the end of the text once per bracket.
_LINK_TARGET = re.compile(r"\]\([^()\[\]\s]+\)")
_BARE_URL = re.compile(r"https?://\S+")
_DATE_ISO = re.compile(r"(?<![\w.])\d{4}-\d{2}-\d{2}(?!\d)")
_DATE_DOTTED = re.compile(r"(?<![\w.])\d{1,2}\. ?\d{1,2}\. ?\d{4}(?!\d)")
# A word, its hyphen-joined digit run, and its dot- or comma-joined digit tail (v1.2.3,
# Qwen3,5, COVID-19.5). Whether the word holds a digit and a letter, or is a capitalised
# name before a hyphen and digits, is decided in _drop_words. A hyphen-joined digit run
# is left out when a word character follows it (870-14cm.104), so that the mixed word
# 14cm.104 is found whole.
_WORD = re.compile(_LABEL, re.IGNORECASE)
_CITED_RANGE = re.compile(r"(\d{1,3})(?:\s*[-\u2013]\s*(\d{1,3}))?")

# What is dropped from an answer before its numbers are scanned. A link's target stops
# at the first bracket, parenthesis or space, so that a text made of unclosed "](" never
# makes the scan run to the end of the text once per bracket.
_LINK_TARGET = re.compile(r"\]\([^()\[\]\s]+\)")
_BARE_URL = re.compile(r"https?://\S+")
_DATE_ISO = re.compile(r"(?<![\w.])\d{4}-\d{2}-\d{2}(?!\d)")
_DATE_DOTTED = re.compile(r"(?<![\w.])\d{1,2}\. ?\d{1,2}\. ?\d{4}(?!\d)")
# A word, its hyphen-joined digit run, and its dot- or comma-joined digit tail (v1.2.3,
# Qwen3,5, COVID-19.5). Whether the word holds a digit and a letter, or is a capitalised
# name before a hyphen and digits, is decided in _drop_words. A word never starts right
# after a number or a dot (12.5m2, x.y6_1), so a number glued to a unit is left to the
# neighbour rule of _scan_numbers. A hyphen-joined digit run is left out when a word
# character follows it (870-14cm.104), so that the mixed word 14cm.104 is found whole.
_WORD = re.compile(_LABEL, re.IGNORECASE)
_CITED_RANGE = re.compile(r"(\d{1,3})(?:\s*[-\u2013]\s*(\d{1,3}))?")

# What is dropped from an answer before its numbers are scanned. A link's target stops
# at the first bracket, parenthesis or space, so that a text made of unclosed "](" never
# makes the scan run to the end of the text once per bracket.
_LINK_TARGET = re.compile(r"\]\([^()\[\]\s]+\)")
_BARE_URL = re.compile(r"https?://\S+")
_DATE_ISO = re.compile(r"(?<![\w.])\d{4}-\d{2}-\d{2}(?!\d)")
_DATE_DOTTED = re.compile(r"(?<![\w.])\d{1,2}\. ?\d{1,2}\. ?\d{4}(?!\d)")
# A word, its hyphen-joined digit run, and its dot- or comma-joined digit tail (v1.2.3,
# Qwen3,5, COVID-19.5). Whether the word holds a digit and a letter, or is a capitalised
# name before a hyphen and digits, is decided in _drop_words. A word never starts right after a number or a
# dot (12.5m2, x.y6_1), so a number glued to a unit is left to the neighbour rule of
# _scan_numbers. A hyphen-joined digit run is left out when a word character follows it
# (870-14cm.104), so that the mixed word 14cm.104 is found whole.
_WORD = re.compile(r"(?<![\w.])(\w+)(-\d+(?!\w))?((?:[.,]\d+)*)")
# What replaces a dropped token: neither whitespace nor a letter, so that a hyphen right
# after it does not read as a sign, and the digits around it do not run together.
_DROPPED = "\x00"
# A list number at the start of a line: 1. or 2) or (3), behind any markdown decoration.
_LIST_MARKER = re.compile(r"^[>#*_\- \t]*(\()?\d+([.)])[*_]*\s", re.MULTILINE)
# An ordinal inside a sentence, as Czech writes it: one or two digits, a dot, then
# whitespace on the same line. Whether it is one is decided by the case of the next letter.
_ORDINAL = re.compile(r"(?<![\d.,])\d{1,2}\.([^\S\r\n]+)(\S)")
# A markdown link's target, when it directly follows a citation.
_LINK_AFTER = re.compile(r"\([^()\[\]\s]*\)")

# The forms of a number, tried in this order at each position (the first that matches
# wins), and the pattern of each. Only the caller of _read decides what a form means.
_SPACE = "[ \u00a0\u202f]"
_NUMBER_FORMS = {
    "spaced": rf"\d{{1,3}}(?:{_SPACE}\d{{3}})+(?!\d)(?:[.,]\d+)?",
    "grouped": r"\d{1,3}(?:,\d{3})+\.\d+",
    "dotted": r"[1-9]\d{0,2}(?:\.\d{3})+,\d+(?!\d|[.,]\d)",
    "commas": r"\d+(?:\.\d+)?(?:,\d+(?:\.\d+)?)+",
    "dotgroup": r"\d{1,3}(?:\.\d{3})+(?!\d)",
    "plain": r"\d+(?:\.\d+)?",
}
_NUMBER = re.compile("|".join(f"(?P<{form}>{pattern})" for form, pattern in _NUMBER_FORMS.items()))
_ZERO_LED_GROUP = re.compile(r"0\d\d")
_LETTER_OR_UNDERSCORE = re.compile(r"[^\W\d]")
_MINUS_SIGNS = "-\u2212"
_SIGN_PREFIXES = "([{=,;:"


def _cited_numbers(content: str) -> set[int] | None:
    """Read the integers a bracket names, if the bracket is citation-like.

    :param content: The text between the brackets.
    :return: The named integers, ranges expanded, or None when the bracket is not a
        citation (a decimal, four digits, words).
    """
    if _CITATION_CONTENT.fullmatch(content) is None:
        return None
    numbers: set[int] = set()
    for found in _CITED_RANGE.finditer(_LABEL_WORD.sub("", content)):
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
    Every number in a bracket may carry its own label (``[Source 1, Source 2]``), but
    the label must be one of a fixed set of source words (source, doc, ref, reference,
    excerpt, passage and their Czech and Russian counterparts, in any case): any other
    word makes the bracket ordinary text, as in ``[lower 6, upper 11]``.
    Known limits: a square-bracketed group of bare integers is read as a citation, so a
    fuzzy number written ``[6, 8, 11]`` is misread; and the full-width form with a
    dagger, a number followed by a dagger and a word inside full-width brackets, as some
    models write it, is not read.

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


def _read_spaced(text: str) -> list[list[Decimal]]:
    """Read ``1 000`` or ``1 000,5``: one number, or a list when no group starts with 0.

    A dot decimal after the last group (``56 123.025``) is read the same way, as one
    number or as a list of two, because a table of numbers separated by spaces looks
    like a number written with space-grouped thousands.

    :param text: The matched text.
    :return: The readings.
    """
    groups = re.split(_SPACE, text)
    readings = [[Decimal(re.sub(_SPACE, "", text).replace(",", "."))]]
    if not any(group.startswith("0") for group in groups[1:]):
        readings.append([Decimal(group.replace(",", ".")) for group in groups])
    return readings


def _read_grouped(text: str) -> list[list[Decimal]]:
    """Read ``1,234.56``: comma-grouped thousands with a dot decimal.

    :param text: The matched text.
    :return: The one reading.
    """
    return [[Decimal(text.replace(",", ""))]]


def _read_dotted(text: str) -> list[list[Decimal]]:
    """Read ``1.000,50``: dot-grouped thousands with a decimal comma.

    :param text: The matched text.
    :return: The one reading.
    """
    return [[Decimal(text.replace(".", "").replace(",", "."))]]


def _read_dotgroup(text: str) -> list[list[Decimal]]:
    """Read ``1.234`` or ``12.345.678``: a decimal, or thousands, or both.

    A single dot group may be a decimal; several can only be thousands, and a thousands
    number never starts with zero.

    :param text: The matched text.
    :return: The readings.
    """
    readings: list[list[Decimal]] = []
    if not text.startswith("0"):
        readings.append([Decimal(text.replace(".", ""))])
    if text.count(".") == 1:
        readings.append([Decimal(text)])
    return readings


def _read_commas(text: str) -> list[list[Decimal]]:
    """Read comma-joined digit groups: a list, a decimal comma, or thousands.

    A later part of exactly three digits that starts with zero is a thousands group and
    never a list member; a part such as ``0.5`` is a decimal, not such a group. Parts
    with a dot decimal can only be a list.

    :param text: The matched text.
    :return: The readings.
    """
    parts = text.split(",")
    zero_led = any(_ZERO_LED_GROUP.fullmatch(part) for part in parts[1:])
    readings = [] if zero_led else [[Decimal(part) for part in parts]]
    if "." in text:
        return readings
    if len(parts) == 2:
        readings.append([Decimal(f"{parts[0]}.{parts[1]}")])
    thousands = len(parts[0]) <= 3 and all(len(part) == 3 for part in parts[1:])
    if thousands and not parts[0].startswith("0"):
        readings.append([Decimal("".join(parts))])
    return readings


def _read_plain(text: str) -> list[list[Decimal]]:
    """Read ``14`` or ``14.19``.

    :param text: The matched text.
    :return: The one reading.
    """
    return [[Decimal(text)]]


_READERS: dict[str, Callable[[str], list[list[Decimal]]]] = {
    "spaced": _read_spaced,
    "grouped": _read_grouped,
    "dotted": _read_dotted,
    "commas": _read_commas,
    "dotgroup": _read_dotgroup,
    "plain": _read_plain,
}


def _readings(form: str, text: str, negative: bool) -> list[list[Decimal]]:
    """List the ways a matched number can be read.

    :param form: Which form matched, a key of ``_NUMBER_FORMS``.
    :param text: The matched text, without a sign.
    :param negative: Whether the number carries a minus sign.
    :return: The readings, each a list of numbers.
    """
    readings = _READERS[form](text)
    if negative:
        readings = [[reading[0].copy_negate(), *reading[1:]] for reading in readings]
    return readings


def _has_minus_sign(text: str, start: int) -> bool:
    """Tell whether a minus directly before a number is its sign.

    It is when it opens the text or follows whitespace, an opening bracket, an equals
    sign, a comma, a semicolon or a colon (``lower=-2.50``, ``(-5,-3)``, ``peak:-3``);
    in ``20-40`` it is a range.

    :param text: The scanned text.
    :param start: Index of the number's first digit.
    :return: True when the character before the digit is a sign.
    """
    if start == 0 or text[start - 1] not in _MINUS_SIGNS:
        return False
    return start == 1 or text[start - 2].isspace() or text[start - 2] in _SIGN_PREFIXES


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


def strip_citations(text: str) -> str:
    """Remove citation-like brackets from a text, and the target of a link after one.

    The brackets are those :func:`check_citations` reads. A bracket that is not a
    citation, such as ``[11.54, 14.19]``, stays. The number check uses this for its own
    citation step, and the chat service uses it on earlier answers in the history,
    whose ``[n]`` numbers mean nothing in a new turn.

    :param text: The text to clean.
    :return: The text with each citation replaced by one space.
    """
    return _replace_citations(text, " ")


def _replace_citations(text: str, filler: str) -> str:
    """Replace each citation-like bracket, and the link target after it, by a filler.

    :param text: The text to clean.
    :param filler: What stands in place of each citation.
    :return: The cleaned text.
    """
    pieces: list[str] = []
    position = 0
    for start, end, _numbers in _citation_spans(text):
        if start < position:
            continue
        link = _LINK_AFTER.match(text, end)
        pieces.append(text[position:start])
        pieces.append(filler)
        position = link.end() if link else end
    pieces.append(text[position:])
    return "".join(pieces)


def _drop_ordinals(text: str) -> str:
    """Remove ordinals such as ``2.`` in ``Ve 2. kroku``.

    A number and a dot followed by a lowercase letter is an ordinal; one followed by an
    uppercase letter ends a sentence, and its number stays.

    :param text: The text to clean.
    :return: The text without the ordinals.
    """
    return _ORDINAL.sub(lambda match: match[1] + match[2] if match[2].islower() else match[0], text)


def _drop_words(text: str) -> str:
    """Remove the digits of names and identifiers, such as ``v1.2.3`` or ``COVID-19``.

    A word that holds both a letter and a digit (``v1``, ``Qwen3``, ``doc1``, ``1st``,
    ``H2O``) stays as it is, because the neighbour rule of :func:`_scan_numbers` already
    skips the digits glued to its letters; only its dot- or comma-joined digit tail
    (``v1.2.3``, ``Qwen3,5``) is replaced by a filler, so that the tail is not read as a
    number of its own. A hyphen-joined digit run after such a word stays and is checked.
    A word made of letters that starts with a capital, a hyphen and a digit run
    (``COVID-19``, ``GPT-4``, ``ISO-8601``, ``\u010cSN-73``) is a name and goes whole. A
    lowercase word before a hyphen (``error-15.3``, ``peak-3``, ``n-1``) is not a name.
    A word that starts right after a number or a dot (``84.3W-1``, ``12.5m2``) is left
    alone: the number glued to it is judged by the neighbour rule.

    :param text: The text to clean.
    :return: The text with each dropped token replaced by a filler.
    """

    def replace(match: re.Match[str]) -> str:
        word, hyphen, tail = match.groups()
        if not word.isdecimal() and any(char.isdecimal() for char in word):
            return match[0] if hyphen else word + (_DROPPED if tail else "")
        if hyphen and word.isalpha() and word[0].isupper():
            return _DROPPED
        return match[0]

    return _WORD.sub(replace, text)


def _strip_answer(answer: str) -> str:
    """Remove what is not a data point from an answer, before its numbers are scanned.

    The drops run in this order: the target of every markdown link, bare URLs,
    citation-like brackets, dates, words that hold digits, list numbering (``1.``,
    ``2)``, ``(3)``, behind markdown decoration), and last ordinals. Links and URLs go
    first so that a digit in an address is never read; citations go before the words
    because ``[doc1]`` is a citation; dates and words go before numbering and ordinals
    because those match on a number and a dot. A dropped token leaves a filler that is
    not whitespace, so a hyphen right after it (``doc1-5``) is not read as a minus sign.

    :param answer: The model's final answer text.
    :return: The cleaned text.
    """
    text = _LINK_TARGET.sub("]", answer)
    text = _BARE_URL.sub(_DROPPED, text)
    text = _replace_citations(text, _DROPPED)
    text = _DATE_ISO.sub(_DROPPED, text)
    text = _DATE_DOTTED.sub(_DROPPED, text)
    text = _drop_words(text)
    text = _LIST_MARKER.sub(lambda match: match[0] if match[1] and match[2] == "." else "", text)
    return _drop_ordinals(text)


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

    Before scanning, the answer loses the target of markdown links, bare URLs,
    citation-like brackets (see :func:`strip_citations`), dates, the dot- or comma-joined
    digit tail of an identifier (``v1.2.3``, ``Qwen3,5``), names that start with a
    capital of any script before a hyphen and digits (``COVID-19``), list numbering and
    ordinals; the order is in ``_strip_answer``. A number is then a digit run, with a
    sign when a minus opens the text or follows whitespace, an opening bracket, an
    equals sign or a separator (comma, semicolon, colon), and never one that sits next
    to a letter or an underscore, so a number glued to a unit (``8mm``, ``5 000km``,
    ``12.5m2``) is not checked. The digit class of the patterns matches every Unicode
    decimal digit, full-width ones included, and stays that way because the patterns
    also rely on Unicode word characters: a full-width digit is a number like an ASCII
    one. Thousands may be grouped with spaces (``1 000``),
    commas (``1,234.56``) or dots with a decimal comma (``1.000,50``). A token is read
    every way it can be, and is grounded when one reading has all its numbers grounded:
    ``14,19`` is 14.19 or 14 and 19, ``1,234`` is 1234 or 1 and 234, ``1.234`` is 1.234
    or 1234, ``12.345.678`` is only 12345678, ``6,8.75,11`` is three numbers, and
    ``100 200 300`` is one number or three. A group of exactly three digits that starts
    with zero (``5,000,000``, ``5 000``) is a thousands group and never a list member,
    but ``5,000`` still passes when the data holds 5, because a comma before three
    digits may be a decimal comma. ``1.422,7`` is one number with dot-grouped thousands
    and a decimal comma, never a list of two, unless a dot or a comma and a digit
    follow it (``(1.500,2.500)``, ``(1.884,90,12.1)`` are lists).

    A token that fits no reading (``1,000,5``, ``5.5,000``, ``0.000.000``) is reported
    as written, even when the grounding holds the same text.

    A number written with ``d`` decimals is grounded when some number in the grounding
    texts, quantized to ``d`` decimals, equals it under round-half-up or under
    truncation: the data says ``14.1923076923``, so ``14.19``, ``14.2`` and ``14`` are
    grounded and ``15`` is not. Percentages are compared as written: ``0.2`` does not
    ground ``20 %``. Known limits: a square-bracketed group of bare integers, or of
    integers each labelled with a source word, is read as a citation and skipped, so a
    fuzzy number written ``[6, 8, 11]`` is not checked.

    Other known limits: a number spelled as a word is not checked; the check matches a
    bag of numbers, so a grounded number attached to the wrong quantity passes; a
    citation written outside square brackets (``(Source 3)``) is not seen by
    :func:`check_citations`; and a link target that holds a bracket or a parenthesis is
    not recognised as a target (a bare ``http`` address in it is still dropped).

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
