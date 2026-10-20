"""Tests for removing citations from an answer, whole and piece by piece."""

import pytest

from api.assistant.agent.checks import (
    CitationStreamFilter,
    cited_numbers,
    remove_citations,
)

_ANSWERS = [
    "The midpoint [1].",
    "The compromise is the midpoint [1](https://example.org/a) of the median [2], [3].",
    "[1] Starts with a citation.\n[2] [3] And so does this line.\nPlain line.",
    "The range is [11.54, 14.19], see [source 2] and [1-3][4].",
    "Full-width \u30101\u3011 and \u30102, 3\u3011 end the sentence \u30101\u3011",
    "A markdown [link text](https://example.org/b) stays, a [1] (5 experts) goes.",
    "Open bracket [ never closes and neither does [1",
    "Link target [1](https://exa mple stops at the space.",
    "Nested [a [1] b] and a lone ] and a lone [.",
    "Trailing blanks before the end [1]   ",
    "Tabs\t[1]\tand nbsp\u00a0[2]\u00a0here.",
    "No citations here at all, only 5 experts and 11.54.",
    "",
]


class TestRemoveCitations:
    """A citation goes with the blanks before it and the link target after it."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("The midpoint [1].", "The midpoint."),
            ("a [1], b [2][3].", "a, b."),
            ("see [1](https://x/y) now", "see now"),
            ("[1] Start", "Start"),
            ("first\n[1] second", "first\nsecond"),
            ("a [1-3] b [1, 2] c [source 2] d", "a b c d"),
            ("\u30101\u3011 x \u30102, 3\u3011", "x"),
            ("Result [1] (5 experts)", "Result (5 experts)"),
        ],
    )
    def test_removes_the_citation_and_the_blanks_around_it(self, text: str, expected: str):
        """
        GIVEN an answer with citations in several forms and positions
        WHEN the citations are removed
        THEN no marker, link target or doubled blank is left
        """
        assert remove_citations(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "The range is [11.54, 14.19].",
            "A [link](https://example.org) here.",
            "A group [lower 6, upper 11] is words.",
            "No brackets, 5 experts.",
        ],
    )
    def test_keeps_a_bracket_that_is_not_a_citation(self, text: str):
        """
        GIVEN a text whose brackets are decimals, a link or words
        WHEN the citations are removed
        THEN the text is unchanged
        """
        assert remove_citations(text) == text


class TestCitedNumbers:
    """The numbers an answer cites are read as the citation check reads them."""

    def test_lists_every_number_named_with_ranges_expanded(self):
        """
        GIVEN an answer citing 1, a range of 3 to 4 and a labelled 7
        WHEN the cited numbers are listed
        THEN the set holds 1, 3, 4 and 7
        """
        assert cited_numbers("a [1] b [3-4] c [Source 7] d [1.5]") == {1, 3, 4, 7}


class TestCitationStreamFilter:
    """The pieces let out never hold a citation and always add up to the cleaned answer."""

    @staticmethod
    def _run(pieces: list[str]) -> list[str]:
        stream = CitationStreamFilter()
        shown = [stream.feed(piece) for piece in pieces]
        shown.append(stream.finish("".join(pieces)))
        return [piece for piece in shown if piece]

    @staticmethod
    def _assert_clean_and_exact(answer: str, pieces: list[str]) -> None:
        expected = remove_citations(answer)
        assert cited_numbers(expected) == set()
        joined = ""
        for piece in TestCitationStreamFilter._run(pieces):
            joined += piece
            # Every piece extends what was let out, and what is let out is never revised.
            assert expected.startswith(joined), (pieces, joined)
        assert joined == expected, pieces

    @pytest.mark.parametrize("answer", _ANSWERS)
    def test_every_split_in_two_adds_up_to_the_cleaned_answer(self, answer: str):
        """
        GIVEN an answer and every index at which it can be cut in two
        WHEN the two pieces are fed through the filter
        THEN the text let out is at every moment the start of the cleaned answer, and joins to the cleaned answer
        """
        for index in range(len(answer) + 1):
            self._assert_clean_and_exact(answer, [answer[:index], answer[index:]])

    @pytest.mark.parametrize("answer", _ANSWERS)
    def test_one_character_pieces_add_up_to_the_cleaned_answer(self, answer: str):
        """
        GIVEN an answer arriving one character at a time
        WHEN it is fed through the filter
        THEN the text let out is at every moment the start of the cleaned answer, and joins to the cleaned answer
        """
        self._assert_clean_and_exact(answer, list(answer))

    @pytest.mark.parametrize("answer", _ANSWERS)
    def test_every_split_in_three_adds_up_to_the_cleaned_answer(self, answer: str):
        """
        GIVEN an answer cut in three at every pair of indices
        WHEN the pieces are fed through the filter
        THEN the text let out joins to the cleaned answer
        """
        for first in range(0, len(answer) + 1, 2):
            for second in range(first, len(answer) + 1, 3):
                self._assert_clean_and_exact(
                    answer, [answer[:first], answer[first:second], answer[second:]]
                )

    def test_a_citation_split_across_pieces_is_never_let_out(self):
        """
        GIVEN a citation with its link target arriving in four pieces
        WHEN they are fed one after another
        THEN nothing of the citation is let out, and the sentence ends clean
        """
        stream = CitationStreamFilter()

        shown = [
            stream.feed(piece) for piece in ("The midpoint [", "1", "](https://example.org/a)", ".")
        ]

        assert shown == ["The midpoint", "", "", "."]
        assert stream.finish("The midpoint [1](https://example.org/a).") == ""

    def test_it_reports_whether_a_piece_was_fed(self):
        """
        GIVEN a new filter
        WHEN a piece is fed
        THEN it was not started before and is after
        """
        stream = CitationStreamFilter()
        before = stream.started

        stream.feed("Text")

        assert (before, stream.started) == (False, True)
