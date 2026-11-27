"""Tests for the number check's treatment of verbatim copies of a name, and for NumberCheck."""

import time

import pytest

from api.assistant.agent.checks import NumberCheck, find_ungrounded_numbers, numbers_in

_B = "Budget 2027"
_GAPS = ("\n", "\t", "   ", " \n ")
_CUT = "Budget 2027 for the flood works at the old..."


def _case(name, answers, copies, expected, grounding=()):
    """Build a row: the answers are checked against the grounding, with the copies given."""
    return pytest.param(answers, copies, expected, grounding, id=name)


# fmt: off
_CASES = [
    # A copy is masked.
    _case("no-copy-reports", "The project Budget 2027 is open.", (), ["2027"]),
    _case("copy-masked", "The project Budget 2027 is open.", (_B,), []),
    _case("number-outside-reported", "Budget 2027 closes in 2027.", (_B,), ["2027"]),
    _case("every-occurrence", "Budget 2027 and again Budget 2027.", (_B,), []),
    _case("at-the-edges", ("Budget 2027", "Budget 2027 is the one.", "It is Budget 2027"), (_B,), []),
    _case("accents", "Projekt Rozpo\u010det 2027 b\u011b\u017e\u00ed.", ("Rozpo\u010det 2027",), []),
    _case("invisible-inside", "Budget\u200b 2027 is open.", (_B,), []),
    _case("emphasis-around", ("The **Budget 2027** is open.", "The _Budget 2027_ is open."), (_B,), []),
    _case("link-text", "See [Budget 2027](https://example.org/a).", (_B,), []),
    _case("citation-bracket", "See [Budget 2027] today.", (_B,), []),
    # What counts as a name: 4 characters and a letter. The words and their order do not matter,
    # because nothing is hidden by a copy any more: its digits get a line of their own.
    _case("number-first-word", "The 2027 Budget is open.", ("2027 Budget",), []),
    _case("currency-claim", "The best compromise is 7351 CZK.", ("7351 CZK",), []),
    _case("digit-in-first-word", "It is Q4 2027 now.", ("Q4 2027",), []),
    _case("one-word-field", "The budget-2027 is open.", ("budget-2027",), []),
    _case("phrase-name", "The best compromise is 7351.", ("is 7351",), []),
    # A copy must be exact.
    _case("other-case", "The project budget 2027 is open.", (_B,), ["2027"]),
    _case("markdown-inside", ("The **Budget** 2027 is open.", "The Budget **2027** is open."), (_B,), ["2027"]),
    _case("other-word", "The plan 2027 is open.", (_B,), ["2027"]),
    _case("whitespace-run", tuple(f"Budget{gap}2027 Q4 is open." for gap in _GAPS), ("Budget 2027 Q4",), []),
    # A digit or a joiner right after the copy cancels it: the neighbour is grounded, so
    # only the copy's own number can be reported.
    _case("after-digit", "Budget 20271 is open.", (_B,), ["20271"], ["1"]),
    _case("after-dot", "Budget 2027.5 is open.", (_B,), ["2027.5"], ["5"]),
    _case("after-comma", "Budget 2027,5 is open.", (_B,), ["2027,5"], ["5"]),
    _case("after-hyphen", "Budget 2027-5 is open.", (_B,), ["2027"], ["5"]),
    _case("after-slash", "Budget 2027/5 is open.", (_B,), ["2027"], ["5"]),
    _case("after-colon", "Budget 2027:5 is open.", (_B,), ["2027"], ["5"]),
    _case("after-space", "Budget 2027 5 is open.", (_B,), ["2027"], ["5"]),
    _case("after-percent", "Budget 2027% is open.", (_B,), ["2027"]),
    _case("after-spaced-percent", "Budget 2027 % is open.", (_B,), ["2027"]),
    _case("after-per-mille", "Budget 2027\u2030 is open.", (_B,), ["2027"]),
    _case("after-no-break-space", "Budget 2027\u00a05 is open.", (_B,), ["2027"], ["5"]),
    _case("after-narrow-no-break-space", "Budget 2027\u202f5 is open.", (_B,), ["2027"], ["5"]),
    _case("after-en-dash", "Budget 2027\u20135 is open.", (_B,), ["2027"], ["5"]),
    _case("after-minus", "Budget 2027\u22125 is open.", (_B,), ["2027"], ["5"]),
    # A digit and a joiner right before the copy cancel it; so does a letter or a digit.
    _case("before-space", "It costs 7 Budget 2027.", (_B,), ["2027"], ["7"]),
    _case("before-hyphen", "It is 7-Budget 2027.", (_B,), ["2027"], ["7"]),
    _case("before-slash", "It is 7/Budget 2027.", (_B,), ["2027"], ["7"]),
    _case("before-colon", "It is 7:Budget 2027.", (_B,), ["2027"], ["7"]),
    _case("before-dot", "It is 7.Budget 2027.", (_B,), ["2027"], ["7"]),
    _case("before-comma", "It is 7,Budget 2027.", (_B,), ["2027"], ["7"]),
    _case("before-no-break-space", "It costs 7\u00a0Budget 2027.", (_B,), ["2027"], ["7"]),
    _case("before-narrow-no-break-space", "It costs 7\u202fBudget 2027.", (_B,), ["2027"], ["7"]),
    _case("before-en-dash", "It is 7\u2013Budget 2027.", (_B,), ["2027"], ["7"]),
    _case("before-minus", "It is 7\u2212Budget 2027.", (_B,), ["2027"], ["7"]),
    _case("longer-number-before", "It costs 7 500 CZK.", ("500 CZK",), ["7 500"]),
    _case("before-letter", "The XBudget 2027 is open.", (_B,), ["2027"]),
    _case("before-digit", "The 9Budget 2027 is open.", (_B,), ["2027"]),
    # What does not cancel it.
    _case("comma-and-space-after", "Budget 2027, 14.19 spent.", (_B,), ["14.19"]),
    _case("underscores", "Name: _Budget 2027_.", (_B,), []),
    _case("punctuation", ('"Budget 2027".', "(Budget 2027)", "Budget 2027.", "Budget 2027!"), (_B,), []),
    _case("adjacent-copies", "Budget 2027 Budget 2028", ("Budget 2027", "Budget 2028"), ["2028"]),
    # A field of under 4 characters hides nothing.
    _case("short-5", "Item 5 is open.", ("5",), ["5"]),
    _case("short-12", "Item 12 is open.", ("12",), ["12"]),
    _case("no-letter-2027", "In 2027 we go.", ("2027",), ["2027"]),
    _case("no-letter-12.5", "A width of 12.5 is set.", ("12.5",), ["12.5"]),
    _case("three-chars-Q7", "The Q 7 is open.", ("Q 7",), ["7"]),
    _case("three-chars-A1", "The A 1 is open.", ("A 1",), ["1"]),
    _case("only-dots", "Wait... 7 more.", ("...",), ["7"]),
    _case("short-prefix", "Plan ab 7 more.", ("ab...",), ["7"]),
    _case("empty", "Wait 7 more.", ("",), ["7"]),
    _case("four-chars-count", "The Q 77 is open.", ("Q 77",), []),
    # A cut field is matched by its prefix.
    _case("cut-without-dots", "The Budget 2027 for the flood works at the old mill.", (_CUT,), []),
    _case("cut-with-dots", "The Budget 2027 for the flood works at the old... is open.", (_CUT,), []),
    _case("cut-prefix-too-short", "Plan 7 is it.", ("7 a...",), ["7"]),
    # The longest copy goes first, in whatever order the copies come.
    _case("longest-first", "See Plan 2027 Q 4 today.", ("Plan 2027", "Plan 2027 Q 4"), []),
    _case("longest-first-reversed", "See Plan 2027 Q 4 today.", ("Plan 2027 Q 4", "Plan 2027"), []),
    _case("shorter-alone", "See Plan 2027 Q 4 today.", ("Plan 2027",), ["4"]),
    _case("shorter-where-longer-misses", "See Plan 2027 today.", ("Plan 2027 Q 4", "Plan 2027"), []),
    _case("repeated-copy", "See Plan 2027 today.", ("Plan 2027",) * 3, []),
    # A copy must not change how the rest of the text is read.
    _case("url-swallows-its-copy", "https://x.y/Budget 2027;99999", (_B,), []),
    _case("name-in-a-url-path", "See https://x.y/Jana/reports/2024 now", ("Jana",), []),
    _case("ordinal-before-lowercase-copy", "Podle 2. pilot 2027 vysly dobre.", ("pilot 2027",), []),
    _case("ordinal-before-lowercase-name", "See 3. van der Berg gave 5.", ("van der Berg",), [], ["5"]),
    _case("sentence-end-before-capital-copy", "See 3. Budget 2027 now.", (_B,), ["3"]),
    # A copy grounds nothing.
    _case("number-alone", "The figure is 2027.", (_B,), ["2027"]),
]
# fmt: on


class TestCopies:
    """A number inside a verbatim copy of a name the model was shown is part of the name."""

    @pytest.mark.parametrize(("answers", "copies", "expected", "grounding"), _CASES)
    def test_the_answer_is_checked_against_the_copies(self, answers, copies, expected, grounding):
        """
        GIVEN an answer, or several, and the copies given with them (the table above: copy
              masked or not, what counts as a name, exactness, boundaries, minimum length, cut
              field, longest first) and the grounding it has, if any
        WHEN each is checked
        THEN it reports exactly what the table says: nothing for a masked copy, the number
             for a copy that does not hold
        """
        for answer in [answers] if isinstance(answers, str) else answers:
            reported = find_ungrounded_numbers(answer, list(grounding), copies=list(copies))
            assert reported == expected, answer

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


def _merge(name, first, second, expected):
    """Build a row from three-list tuples: ungrounded, from a project name, from an expert name."""
    return pytest.param(NumberCheck(*first), NumberCheck(*second), NumberCheck(*expected), id=name)


# fmt: off
_MERGE_CASES = [
    _merge("disjoint-join-in-order", (["1"], ["2"], ["3"]), (["4"], ["5"], ["6"]),
           (["1", "4"], ["2", "5"], ["3", "6"])),
    _merge("ungrounded-once", (["1"], [], []), (["1", "2"], [], []), (["1", "2"], [], [])),
    _merge("real-only-in-the-second", ([], ["7"], []), (["7"], [], []), (["7"], [], [])),
    _merge("real-only-in-the-first", (["7"], [], []), ([], ["7"], []), (["7"], [], [])),
    _merge("real-leaves-the-expert-list", ([], [], ["7"]), (["7"], [], []), (["7"], [], [])),
    _merge("project-wins-over-expert", ([], ["7"], []), ([], [], ["7", "8"]), ([], ["7"], ["8"])),
    _merge("a-name-number-once", ([], ["7", "7"], []), ([], ["7"], []), ([], ["7"], [])),
]
# fmt: on


class TestNumbersIn:
    """The numbers a name holds are what the scan reads in the name alone."""

    @pytest.mark.parametrize(
        ("names", "expected"),
        [
            (["Budget 2027", "7351 CZK"], {"2027", "7351"}),
            (["Q4 2027", "Alpha"], {"2027"}),
            (["https://x.y/z", "Plan 2028 and 2029..."], {"2028", "2029"}),
            (["is 7351", ""], {"7351"}),
            ([], set()),
        ],
    )
    def test_the_numbers_are_the_written_forms(self, names, expected):
        """
        GIVEN names (digits in the middle or at the start, glued to a letter, in a URL, none)
        WHEN the numbers they hold are read
        THEN they are the numbers the scan finds in each name on its own, as written
        """
        assert numbers_in(names) == expected


class TestKeptCopies:
    """A kept copy takes part in the longest-first match but stays visible to the scan."""

    @pytest.mark.parametrize(
        ("answer", "copies", "kept", "expected"),
        [
            pytest.param(
                "The Budget 2027 plan is open.",
                ("Budget 2027",),
                ("Budget 2027 plan",),
                ["2027"],
                id="longer-kept-copy-shields-the-shorter-one",
            ),
            pytest.param(
                "The Budget 2027 is open.",
                ("Budget 2027",),
                ("Budget 2027 plan",),
                [],
                id="shorter-copy-masks-where-the-longer-misses",
            ),
            pytest.param(
                "The Budget 2027 is open.",
                ("Budget 2027",),
                ("Budget 2027",),
                ["2027"],
                id="a-name-in-both-is-kept",
            ),
        ],
    )
    def test_the_kept_copies_are_found_and_not_masked(self, answer, copies, kept, expected):
        """
        GIVEN copies to mask and kept copies that may be longer than them
        WHEN an answer repeating one of them is checked
        THEN a match of a kept copy stays visible and hides nothing under it, and only
             a match of a masked copy is dropped
        """
        assert find_ungrounded_numbers(answer, [], copies=copies, kept=kept) == expected


class TestNumberCheckMerge:
    """The two passes of a turn (the text and the text as shown) merge into one check."""

    @pytest.mark.parametrize(("first", "second", "expected"), _MERGE_CASES)
    def test_the_passes_merge_into_three_disjoint_lists(self, first, second, expected):
        """
        GIVEN the checks of two passes (the table above: disjoint lists, a repeat, a number
              real in only one of the passes, a number named for different sources)
        WHEN they merge
        THEN a number real in either pass is reported as ungrounded only, a number named by
             both a project and an expert is the project's, and no number repeats or sits in
             two lists
        """
        merged = first.merge(second)

        assert merged == expected
        lists = [merged.ungrounded, merged.project_name, merged.expert_name]
        flat = [number for numbers in lists for number in numbers]
        assert len(flat) == len(set(flat))
