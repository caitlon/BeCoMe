"""Generated answers pin two invariants of the number check.

Both run on a fixed seed, so a failure names the same input every time.

1. An answer used as its own grounding is never reported, except for a token that fits
   no reading at all (``1,000,5``), which is reported as written by design.
2. An answer built only from numbers whose values are in the grounding is never reported,
   whatever format each number is written in.
"""

import random
import re
from decimal import Decimal

from api.assistant.agent.checks import _scan_numbers, find_ungrounded_numbers

_SEED = 20260930
_CASES = 3000

_NBSP = chr(0xA0)
_NNBSP = chr(0x202F)
_MINUS = chr(0x2212)
_EN_DASH = chr(0x2013)
_FULL_WIDTH = [chr(0x3010), chr(0x3011)]

# Characters that make the interesting shapes: digits, separators, brackets, signs,
# letters, spaces of three kinds, line breaks, list and markdown decoration.
_ALPHABET = (
    list("0123456789") * 4
    + list("..,,;:  ")
    + list("---()[]")
    + [_MINUS, _EN_DASH, _NBSP, _NNBSP, *_FULL_WIDTH]
    + list("abxmceQWA_%=#*>\n")
    + list("1. ")
)

# The one shape that reads two ways and is read one way on purpose: a dot-grouped number
# with a decimal comma (1.422,7) is one number, not a list of 1.422 and 7.
_FORMATS = (
    "dot",
    "comma",
    "space",
    "nbsp",
    "nnbsp",
    "spacedot",
    "commas",
    "dots",
    "percent",
    "negative",
    "minus",
)

_DOTTED = re.compile(r"[1-9]\d{0,2}(?:\.\d{3})+,\d")


def _has_no_reading(token: str) -> bool:
    """Tell whether a reported token is one of the forms that fit no reading."""
    return any(not scanned.readings for scanned in _scan_numbers(token.lstrip("-" + _MINUS)))


def _random_string(rng: random.Random) -> str:
    return "".join(rng.choice(_ALPHABET) for _ in range(rng.randint(1, 40)))


def _value(rng: random.Random) -> Decimal:
    kind = rng.random()
    if kind < 0.3:
        return Decimal(rng.randint(0, 99))
    if kind < 0.5:
        return Decimal(rng.randint(100, 9999999))
    places = rng.choice([1, 2, 2, 3])
    whole = rng.choice([0, 0, 1, 5, 12, 97, 123, 1234, 12345])
    return Decimal(f"{whole}.{rng.randint(0, 10**places - 1):0{places}d}")


def _group(digits: str, separator: str) -> str:
    groups: list[str] = []
    while len(digits) > 3:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    return separator.join([digits, *groups])


def _plain(value: Decimal) -> str:
    return format(value, "f")


def _formatted(value: Decimal, rng: random.Random) -> tuple[str, str]:
    """Write a value in a random format, and say how the grounding writes it."""
    whole, _, fraction = _plain(value).partition(".")
    dot = f"{whole}.{fraction}" if fraction else whole
    kind = rng.choice(_FORMATS)
    written = {
        "dot": dot,
        "comma": f"{whole},{fraction}" if fraction else whole,
        "space": _group(whole, " ") + (f",{fraction}" if fraction else ""),
        "nbsp": _group(whole, _NBSP) + (f",{fraction}" if fraction else ""),
        "nnbsp": _group(whole, _NNBSP) + (f",{fraction}" if fraction else ""),
        "spacedot": _group(whole, " ") + (f".{fraction}" if fraction else ""),
        "commas": _group(whole, ",") + (f".{fraction}" if fraction else ""),
        "dots": _group(whole, ".") + (f",{fraction}" if fraction else ""),
        "percent": dot + "%",
        "negative": "-" + dot,
        "minus": _MINUS + dot,
    }[kind]
    grounding = ("-" if kind in ("negative", "minus") else "") + dot
    return written, grounding


def _compound(rng: random.Random) -> tuple[str, list[str]]:
    """A range, a compact or spaced list, an interval or a triplet, with its grounding."""
    a, b, c = _value(rng), _value(rng), _value(rng)
    if rng.random() < 0.5:
        b, c = abs(b), abs(c)
    kind = rng.choice(["range", "compact", "spaced", "interval", "czech", "hundreds"])
    if kind == "range":
        text = f"{_plain(a)}{rng.choice(['-', _EN_DASH])}{_plain(b)}"
    elif kind == "compact":
        text = "(" + ",".join(_plain(x) for x in (a, b, c)) + ")"
    elif kind == "spaced":
        text = "(" + ", ".join(_plain(x) for x in (a, b, c)) + ")"
    elif kind == "interval":
        text = rng.choice("[(") + _plain(a) + rng.choice([",", ", ", "; "]) + _plain(b)
        text += rng.choice("])")
    elif kind == "czech":
        text = "(" + "; ".join(_plain(x).replace(".", ",") for x in (a, b, c)) + ")"
    else:
        a, b, c = (Decimal(rng.randint(100, 999)) for _ in range(3))
        text = f"({a} {b} {c})"
    if _DOTTED.search(text):
        text = text.replace(",", ", ")
    return text, [_plain(x) for x in (a, b, c)]


def _built_answer(rng: random.Random) -> tuple[str, str]:
    """An answer made only of formatted numbers, and a grounding that holds their values."""
    items: list[str] = []
    grounding: list[str] = []
    for _ in range(rng.randint(1, 4)):
        if rng.random() < 0.3:
            text, values = _compound(rng)
            grounding.extend(values)
        else:
            text, value = _formatted(_value(rng), rng)
            grounding.append(value)
        items.append(text)
    joiner = rng.choice(["; ", " and ", ", "])
    template = rng.choice(["The values are {}.", "We see {} in the data", "Result: {}", "{}"])
    return template.format(joiner.join(items)), "values " + " ".join(grounding)


class TestGeneratedAnswers:
    """Answers generated from a fixed seed."""

    def test_an_answer_used_as_its_own_grounding_is_never_reported(self):
        """
        GIVEN random strings of digits, separators, brackets, letters and spaces
        WHEN each is used as its own grounding
        THEN nothing is reported, except a token that fits no reading
        """
        rng = random.Random(_SEED)
        failures = []
        for _ in range(_CASES):
            answer = _random_string(rng)
            reported = [
                token
                for token in find_ungrounded_numbers(answer, [answer])
                if not _has_no_reading(token)
            ]
            if reported:
                failures.append((answer, reported))

        assert failures[:5] == []

    def test_a_built_answer_used_as_its_own_grounding_is_never_reported(self):
        """
        GIVEN answers built from formatted numbers
        WHEN each is used as its own grounding
        THEN nothing is reported
        """
        rng = random.Random(_SEED + 1)
        failures = []
        for _ in range(_CASES):
            answer, _grounding = _built_answer(rng)
            reported = find_ungrounded_numbers(answer, [answer])
            if reported:
                failures.append((answer, reported))

        assert failures[:5] == []

    def test_a_built_answer_whose_values_are_in_the_grounding_is_never_reported(self):
        """
        GIVEN answers built only from numbers written in every supported format
        WHEN the grounding holds each number's value
        THEN nothing is reported
        """
        rng = random.Random(_SEED + 2)
        failures = []
        for _ in range(_CASES):
            answer, grounding = _built_answer(rng)
            reported = find_ungrounded_numbers(answer, [grounding])
            if reported:
                failures.append((answer, grounding, reported))

        assert failures[:5] == []

    def test_the_same_answers_are_reported_when_the_grounding_holds_no_number(self):
        """
        GIVEN the built answers again
        WHEN the grounding holds no number at all
        THEN every answer reports at least one number, so the invariant above is not vacuous
        """
        rng = random.Random(_SEED + 2)
        silent = []
        for _ in range(_CASES):
            answer, _grounding = _built_answer(rng)
            if not find_ungrounded_numbers(answer, ["nothing here"]):
                silent.append(answer)

        assert silent[:5] == []
