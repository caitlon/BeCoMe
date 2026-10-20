"""Tests for removing citations from an answer, whole and piece by piece."""

import random
import time

import pytest

from api.assistant.agent import checks
from api.assistant.agent.checks import (
    CitationStreamFilter,
    cited_numbers,
    remove_citations,
)

SOURCES = {1, 2, 3}

_ANSWERS = [
    "The midpoint [1].",
    "The compromise is the midpoint [1](https://example.org/a) of the median [2], [3].",
    "[1] Starts with a citation.\n[2] [3] And so does this line.\nPlain line.",
    "The range is [11.54, 14.19], see [source 2] and [1-3][4].",
    "Full-width \u30101\u3011 and \u30102, 3\u3011 end the sentence \u30101\u3011",
    "A markdown [link text](https://example.org/b) stays, a [1] (5 experts) goes.",
    "Open bracket [ never closes and neither does [1",
    "Link target [1](https://exa mple stops at the space.",
    "Link target [1](https://never.closes",
    "Nested [a [1] b] and a lone ] and a lone [.",
    "Trailing blanks before the end [1]   ",
    "Tabs\t[1]\tand nbsp\u00a0[2]\u00a0here.",
    "No citations here at all, only 5 experts and 11.54.",
    "Nested [[1]2] and [1[2]] and [[1]1] and [ [1] 2] here.",
    "A list:\n  [1] indented item\n\t[2]\ttabbed item\n  [3]\n[1]  x",
    "Crisp [5, 5, 5], [0, 0, 0] and [0, 0] stay; [1, 1], [2] and [7] go.",
    "A fuzzy number [6, 8, 11], a scale [1, 5], [0, 1] and a pair [1, 2] [7].",
    "Mixed [ \u30101\u3011 2] and \u3010 [1] 2\u3011 and [1](\u30102\u3011) here.",
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
            ("a\n  [1] b", "a\n  b"),
            ("  [1] b", "  b"),
            ("[1, 1] and [2] and [7]", "and and"),
            ("a\n  [1]\n[2]  c", "a\n  \nc"),
            ("a [1-3] b [1, 2] c [source 2] d", "a b c d"),
            ("\u30101\u3011 x \u30102, 3\u3011", "x"),
            ("Result [1] (5 experts)", "Result (5 experts)"),
            ("Result [1](a", "Result(a"),
        ],
    )
    def test_removes_the_citation_and_the_blanks_around_it(self, text: str, expected: str):
        """
        GIVEN an answer with citations in several forms and positions
        WHEN the citations are removed
        THEN no marker, link target or doubled blank is left
        """
        assert remove_citations(text, SOURCES) == expected

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
        assert remove_citations(text, SOURCES) == text

    @pytest.mark.parametrize(
        "text",
        [
            "The value lies in [0, 1].",
            "A Likert scale [1, 5] is used.",
            "The fuzzy number [6, 8, 11] is triangular.",
            "The scale is [0, 100].",
            "A pair [1, 5] stays.",
            "A crisp number [5, 5, 5] or [0, 0, 0] or [0, 0] stays.",
        ],
    )
    def test_keeps_numbers_in_brackets_that_are_not_all_sources(self, text: str):
        """
        GIVEN three registered sources and a bracket of several numbers, one not a source
        WHEN the citations are removed
        THEN the bracket stays
        """
        assert remove_citations(text, SOURCES) == text

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("See [1, 2].", "See."),
            ("See [1-3].", "See."),
            ("See [7].", "See."),
            ("See [source 9] and \u301015\u3011.", "See and."),
        ],
    )
    def test_a_single_number_always_goes_and_several_go_only_when_all_are_sources(
        self, text: str, expected: str
    ):
        """
        GIVEN sources 1 to 3
        WHEN citations are removed
        THEN a bracket of one number goes whatever it is, and so does one of several
             numbers that are all sources
        """
        assert remove_citations(text, SOURCES) == expected

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("[[1]2]", ""),
            ("[1[2]]", ""),
            ("[[1]1]", ""),
            ("[ [1] 2]", ""),
            ("a [[1](x) 2] b", "a b"),
            ("a [b [1] c] d", "a [b c] d"),
        ],
    )
    def test_nested_brackets_leave_no_citation(self, text: str, expected: str):
        """
        GIVEN a citation inside another bracket, which becomes a citation once the inner one
              is gone
        WHEN the citations are removed
        THEN neither is left
        """
        assert remove_citations(text, SOURCES) == expected

    @pytest.mark.parametrize("text", _ANSWERS)
    def test_removing_again_changes_nothing(self, text: str):
        """
        GIVEN the result of removing the citations from an answer
        WHEN they are removed again
        THEN the text is the same
        """
        once = remove_citations(text, SOURCES)

        assert remove_citations(once, SOURCES) == once

    def test_random_texts_are_stable_and_independent_of_how_they_are_cut(self):
        """
        GIVEN random texts made of brackets, digits, blanks and link parentheses, each cut
              in random places
        WHEN they are fed to the stream filter
        THEN the pieces join to what the whole text gives, which removing again leaves alone
        """
        rng = random.Random(7)
        alphabet = ["[", "]", "\u3010", "\u3011", "1", "2", "7", " ", ",", "-", "(", ")", "x", "\n"]
        for _ in range(3000):
            text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 24)))
            whole = remove_citations(text, SOURCES)
            assert remove_citations(whole, SOURCES) == whole, text
            cuts = sorted(rng.randint(0, len(text)) for _ in range(rng.randint(0, 4)))
            pieces = [text[a:b] for a, b in zip([0, *cuts], [*cuts, len(text)], strict=True)]
            stream = CitationStreamFilter(SOURCES)
            joined = "".join(stream.feed(piece) for piece in pieces) + stream.finish()
            assert joined == whole, (text, pieces)


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
    """The pieces let out join to the cleaned answer and are never revised."""

    @staticmethod
    def _assert_exact(answer: str, pieces: list[str]) -> None:
        expected = remove_citations(answer, SOURCES)
        stream = CitationStreamFilter(SOURCES)
        joined = ""
        for piece in pieces:
            joined += stream.feed(piece)
            # What is let out is the start of the final text, so nothing is ever taken back.
            assert expected.startswith(joined), (pieces, joined)
        joined += stream.finish()
        assert joined == expected, pieces

    @pytest.mark.parametrize("answer", _ANSWERS)
    def test_every_split_in_two_adds_up_to_the_cleaned_answer(self, answer: str):
        """
        GIVEN an answer and every index at which it can be cut in two
        WHEN the two pieces are fed through the filter
        THEN the text let out is at every moment the start of the cleaned answer, and joins
             to it
        """
        for index in range(len(answer) + 1):
            self._assert_exact(answer, [answer[:index], answer[index:]])

    @pytest.mark.parametrize("answer", _ANSWERS)
    def test_one_character_pieces_add_up_to_the_cleaned_answer(self, answer: str):
        """
        GIVEN an answer arriving one character at a time
        WHEN it is fed through the filter
        THEN the text let out joins to the cleaned answer
        """
        self._assert_exact(answer, list(answer))

    @pytest.mark.parametrize("answer", _ANSWERS)
    def test_every_split_in_three_adds_up_to_the_cleaned_answer(self, answer: str):
        """
        GIVEN an answer cut in three at every pair of indices
        WHEN the pieces are fed through the filter
        THEN the text let out joins to the cleaned answer
        """
        for first in range(0, len(answer) + 1, 2):
            for second in range(first, len(answer) + 1, 3):
                self._assert_exact(answer, [answer[:first], answer[first:second], answer[second:]])

    def test_a_citation_split_across_pieces_is_never_let_out(self):
        """
        GIVEN a citation with its link target arriving in four pieces
        WHEN they are fed one after another
        THEN nothing of the citation is let out, and the sentence ends clean
        """
        stream = CitationStreamFilter(SOURCES)

        shown = [
            stream.feed(piece) for piece in ("The midpoint [", "1", "](https://example.org/a)", ".")
        ]

        assert shown == ["The midpoint", "", "", "."]
        assert stream.finish() == ""

    def test_an_outer_bracket_holds_what_follows_until_it_is_closed(self):
        """
        GIVEN a bracket that opens, holds a citation and is not closed yet
        WHEN the pieces arrive
        THEN nothing after the outer bracket is let out until it closes, and then none of it
             is left
        """
        stream = CitationStreamFilter(SOURCES)

        shown = [stream.feed(piece) for piece in ("Hi [", "[1]", " 2", "]", " there")]

        assert shown == ["Hi", "", "", "", " there"]

    def test_a_full_width_bracket_inside_a_closed_group_holds_nothing_back(self):
        """
        GIVEN a full-width bracket that opens inside a square group and is closed by the
              square one
        WHEN the text after the group arrives
        THEN it is let out at once, as the full-width bracket is ordinary text by then
        """
        stream = CitationStreamFilter(SOURCES)
        text = f"[ {chr(0x3010)} 1] and the rest"

        assert stream.feed(text) == text

    @pytest.mark.parametrize(
        "pieces",
        [
            ["[1] "] * 400,
            [" [", "1", "]"] * 300,
            ["[ "] * 300 + ["1] "] * 300,
            ["["] * 2000 + ["]"] * 2000,
            ["a ["] * 2000 + ["]"] * 2000,
            ["["] * 2000 + [chr(0x3011)] * 2000 + ["]"] * 2000,
            ["[ " + "x" * 10] * 500 + ["]"] * 500,
        ],
    )
    def test_the_work_grows_with_the_text_not_with_the_square_of_it(self, monkeypatch, pieces):
        """
        GIVEN hundreds of pieces, each a citation or part of one, or a deep nest of brackets
              that stay in the text
        WHEN they are fed through the filter
        THEN the text handed to the citation reader adds up to no more than twice the text, as
             it would not if every closing bracket read all that is nested in it
        """
        text = "".join(pieces)
        handed: list[int] = []
        real = checks._cited_numbers
        monkeypatch.setattr(checks, "_cited_numbers", lambda c: handed.append(len(c)) or real(c))
        stream = CitationStreamFilter(SOURCES)

        joined = "".join(stream.feed(piece) for piece in pieces) + stream.finish()
        streamed = sum(handed)

        assert joined == remove_citations(text, SOURCES)
        assert streamed <= 2 * len(text)

    def test_a_long_run_of_blanks_arriving_in_pieces_costs_no_more_than_its_length(self):
        """
        GIVEN thousands of pieces of blanks, which are all held back until text follows
        WHEN they are fed through the filter
        THEN it finishes in a small fraction of the time a rescan of the run per piece takes
             (seconds), and the blanks are let out once the text arrives
        """
        stream = CitationStreamFilter(SOURCES)
        started = time.perf_counter()

        shown = [stream.feed(" " * 16) for _ in range(4000)]
        shown.append(stream.feed("end"))

        assert time.perf_counter() - started < 1.0
        assert "".join(shown) == " " * 64000 + "end"
