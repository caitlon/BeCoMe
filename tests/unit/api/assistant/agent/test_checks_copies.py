"""Tests for the number check's treatment of verbatim copies of a project's free text."""

import time

import pytest

from api.assistant.agent.checks import find_ungrounded_numbers

_B = "Budget 2027"
_GAPS = ("\n", "\t", "   ", " \n ")
# (id, answers, copies, expected): every answer is checked against no grounding at all, and
# `expected` is what it must report, or None for "something".
_CASES = [
    # A copy is masked.
    ("no-copy-reports", "The project Budget 2027 is open.", (), ["2027"]),
    ("copy-masked", "The project Budget 2027 is open.", (_B,), []),
    ("number-outside-reported", "Budget 2027 closes in 2027.", (_B,), ["2027"]),
    ("every-occurrence", "Budget 2027 and again Budget 2027.", (_B,), []),
    ("at-the-edges", ("Budget 2027", "Budget 2027 is the one.", "It is Budget 2027"), (_B,), []),
    ("number-first", "The 2027 Budget is open.", ("2027 Budget",), []),
    ("accents", "Projekt Rozpočet 2027 běží.", ("Rozpočet 2027",), []),
    ("invisible-inside", "Budget​ 2027 is open.", (_B,), []),
    ("emphasis-around", ("The **Budget 2027** is open.", "The _Budget 2027_ is open."), (_B,), []),
    ("link-text", "See [Budget 2027](https://example.org/a).", (_B,), []),
    # A copy must be exact.
    ("other-case", "The project budget 2027 is open.", (_B,), ["2027"]),
    (
        "markdown-inside",
        ("The **Budget** 2027 is open.", "The Budget **2027** is open."),
        (_B,),
        ["2027"],
    ),
    ("other-word", "The plan 2027 is open.", (_B,), ["2027"]),
    (
        "whitespace-run",
        tuple(f"Budget{gap}2027 Q4 is open." for gap in _GAPS),
        ("Budget 2027 Q4",),
        [],
    ),
    # A digit or joiner right after the copy cancels it.
    ("after-digit", "Budget 20271 is open.", (_B,), ["20271"]),
    ("after-dot-digit", "Budget 2027.5 is open.", (_B,), ["2027.5"]),
    ("after-comma-digit", "Budget 2027,5 is open.", (_B,), ["2027,5"]),
    ("after-hyphen-digit", "Budget 2027-5 is open.", (_B,), None),
    ("after-slash-digit", "Budget 2027/5 is open.", (_B,), None),
    ("after-colon-digit", "Budget 2027:5 is open.", (_B,), None),
    ("after-space-digit", "Budget 2027 5 is open.", (_B,), None),
    # A digit and a joiner right before the copy cancel it; so does a letter or digit.
    ("before-group", "It costs 7 500 CZK.", ("500 CZK",), None),
    ("before-hyphen", "It is 10-2027 Budget.", ("2027 Budget",), None),
    ("before-dot", "It is 1.2027 Budget.", ("2027 Budget",), None),
    ("before-comma", "It is 1,2027 Budget.", ("2027 Budget",), None),
    ("before-letter", "The XBudget 2027 is open.", (_B,), ["2027"]),
    ("before-digit", "The 9Budget 2027 is open.", (_B,), ["2027"]),
    # What does not cancel it.
    ("comma-and-space-after", "Budget 2027, 14.19 spent.", (_B,), ["14.19"]),
    ("underscores", "Name: _Budget 2027_.", (_B,), []),
    ("punctuation", ('"Budget 2027".', "(Budget 2027)", "Budget 2027.", "Budget 2027!"), (_B,), []),
    # A field of under 4 characters, or without a letter, hides nothing.
    ("short-5", "Item 5 is open.", ("5",), ["5"]),
    ("short-12", "Item 12 is open.", ("12",), ["12"]),
    ("no-letter-2027", "In 2027 we go.", ("2027",), ["2027"]),
    ("no-letter-12.5", "A width of 12.5 is set.", ("12.5",), ["12.5"]),
    ("three-chars-Q7", "The Q 7 is open.", ("Q 7",), ["7"]),
    ("three-chars-A1", "The A 1 is open.", ("A 1",), ["1"]),
    ("only-dots", "Wait... 7 more.", ("...",), ["7"]),
    ("short-prefix", "Plan ab 7 more.", ("ab...",), ["7"]),
    ("empty", "Wait 7 more.", ("",), ["7"]),
    ("four-chars-count", "The Q 77 is open.", ("Q 77",), []),
    # A cut field is matched by its prefix.
    (
        "cut-without-dots",
        "The Budget 2027 for the flood works at the old mill.",
        ("Budget 2027 for the flood works at the old...",),
        [],
    ),
    (
        "cut-with-dots",
        "The Budget 2027 for the flood works at the old... is open.",
        ("Budget 2027 for the flood works at the old...",),
        [],
    ),
    ("cut-prefix-too-short", "Plan 7 is it.", ("7 a...",), ["7"]),
    # The longest copy goes first, in whatever order the copies come.
    ("longest-first", "See Plan 2027 Q 4 today.", ("Plan 2027", "Plan 2027 Q 4"), []),
    ("longest-first-reversed", "See Plan 2027 Q 4 today.", ("Plan 2027 Q 4", "Plan 2027"), []),
    ("shorter-where-longer-misses", "See Plan 2027 today.", ("Plan 2027 Q 4", "Plan 2027"), []),
    ("repeated-copy", "See Plan 2027 today.", ("Plan 2027",) * 3, []),
    # A copy grounds nothing.
    ("number-alone", "The figure is 2027.", (_B,), ["2027"]),
]


class TestCopies:
    """A number inside a verbatim copy of a name the model was shown is part of the name."""

    @pytest.mark.parametrize(
        ("answers", "copies", "expected"),
        [pytest.param(*case[1:], id=case[0]) for case in _CASES],
    )
    def test_the_answer_is_checked_against_the_copies(self, answers, copies, expected):
        """
        GIVEN an answer, or several, and the copies given with them (the table above: copy
              masked or not, exactness, boundaries, minimum length, cut field, longest first)
        WHEN each is checked against no grounding
        THEN it reports what the table says: nothing for a masked copy, the number for a
             copy that does not hold, something at all where the table says None
        """
        for answer in [answers] if isinstance(answers, str) else answers:
            reported = find_ungrounded_numbers(answer, [], copies=list(copies))
            assert (reported == expected) if expected is not None else reported, answer

    def test_no_copies_is_the_old_behaviour(self):
        """
        GIVEN no copies, given or left out
        WHEN an answer is checked
        THEN the result is the same
        """
        answer = "Budget 2027 holds 3 experts."

        assert find_ungrounded_numbers(answer, []) == find_ungrounded_numbers(answer, [], copies=[])

    def test_many_copies_and_a_long_answer_run_fast(self):
        """
        GIVEN a hundred copies and an answer of a hundred thousand characters
        WHEN it is checked
        THEN it finishes at once
        """
        copies = [f"Project number {i} of the long set" for i in range(100)]
        answer = "Project number 7 of the long " * 4000
        started = time.perf_counter()

        find_ungrounded_numbers(answer, [], copies=copies)

        assert time.perf_counter() - started < 5
