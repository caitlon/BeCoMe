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
    "Names [project_data] and [Project Data](https://x/y) and [a_ij] and [TODO] stay or go.",
    "See [docs](https://docs.example.com/x) and [data] (b) then [Source](u) [1](v) [docs](w",
    "[docs][docs](u)[1](v)[data] [[docs]data](x) [[docs] data] [data\n](y) [docs]\n[docs](",
    "[tool result] Starts\n  [System Instruction] indented [source]\nPlain [search_docs]  ",
    "Nested [[project_data] data] and [a [get_project_result] b] and [project_data",
    "",
]

# Recorded answers of the evaluation run e18 (questions dev-P-01 and dev-P-08), which cite
# the internal tag of the project block as if it were a source.
_RECORDED_EN = (
    "The overall result is a best compromise with a centroid of 30.68, which corresponds to a "
    'Likert reading of 25 ("Rather disagree") [project_data]. The panel shows a "high" '
    "agreement level, indicated by a maximum error of 5.68 [project_data].\n\nRegarding the "
    "lean, the result leans towards **no** (disagreement). Although the arithmetic mean is "
    "higher at 36.36, the median is 25.00, and the final compromise is pulled closer to the "
    "median. With 14 out of 22 experts answering 0 or 25, the panel clearly leans toward "
    "disagreement [1]."
)
_RECORDED_EN_CLEAN = (
    "The overall result is a best compromise with a centroid of 30.68, which corresponds to a "
    'Likert reading of 25 ("Rather disagree"). The panel shows a "high" '
    "agreement level, indicated by a maximum error of 5.68.\n\nRegarding the "
    "lean, the result leans towards **no** (disagreement). Although the arithmetic mean is "
    "higher at 36.36, the median is 25.00, and the final compromise is pulled closer to the "
    "median. With 14 out of 22 experts answering 0 or 25, the panel clearly leans toward "
    "disagreement."
)
_RECORDED_CS = "Maxim\u00e1ln\u00ed chyba (\u0394max) \u010din\u00ed 5,68 [project_data]."
_RECORDED_CS_CLEAN = "Maxim\u00e1ln\u00ed chyba (\u0394max) \u010din\u00ed 5,68."


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
            ("It is 5.68 [project_data].", "It is 5.68."),
            ("see [docs] (https://x/y) now", "see (https://x/y) now"),
            ("a [data]", "a"),
            ("a [project data]\n", "a\n"),
            ("see [1](https://x/y) and [docs]", "see and"),
            ("[tool result] Start", "Start"),
            ("first\n[project_data] second", "first\nsecond"),
            ("a\n  [System Instruction] b", "a\n  b"),
            ("a [project_data] b [search_docs][get_project_result].", "a b."),
            ("a [b [project_data] c] d", "a [b c] d"),
            ("[[project_data] data]", ""),
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
        "name",
        [
            "project_data",
            "project data",
            "Project Data",
            "PROJECT-DATA",
            " project_data ",
            "project result",
            "project_result",
            "tool result",
            "Tool_Result",
            "tool results",
            "search_docs",
            "Search Docs",
            "get_project",
            "list_my_projects",
            "get_project_result",
            "get project opinions",
            "get_project_opinions",
            "System Instruction",
            "system_instructions",
            "source",
            "Sources",
            "doc",
            "DOCS",
            "Document",
            "documents",
            "data",
            "Zdroj",
            "zdroje",
            "project  data",
            "Project\u00a0Data",
            "project \t_ data",
            "tool\u202fresult",
            "tool\u2003result",
            "search \n docs",
        ],
    )
    def test_removes_a_bracket_naming_an_internal_tag_or_tool(self, name: str):
        """
        GIVEN a bracket whose whole content is a name the model writes as a fake citation
        WHEN the citations are removed
        THEN the bracket goes with the blank before it, whatever its case and separators
        """
        assert remove_citations(f"The result is high [{name}].", SOURCES) == "The result is high."

    @pytest.mark.parametrize(
        "text",
        [
            "The entry [a_ij] of the matrix.",
            "The order [A, C, B] is kept.",
            "A placeholder [TODO] stays.",
            "The quartiles [Q1-Q3] stay.",
            "The range [11.54, 14.19] stays.",
            "The method [BeCoMe] stays.",
            "A name [project_data_extra] that only begins like one stays.",
            "A bracket [project] or [result] or [search] alone stays.",
            "Words around [the project data] stay.",
            "Two names in one bracket [project_data, tool_result] stay.",
            "A numbered name [project_data 1] is not removed as a name.",
        ],
    )
    def test_keeps_a_bracket_that_only_resembles_an_internal_name(self, text: str):
        """
        GIVEN a text with a bracketed formula, list, placeholder or word that is not one of
              the fixed internal names
        WHEN the citations are removed
        THEN the text is unchanged
        """
        assert remove_citations(text, SOURCES) == text

    @pytest.mark.parametrize(
        "text",
        [
            "See [docs](https://docs.example.com/x) for more",
            "See [data](https://x/y) for more",
            "See [Source](https://x/y) for more",
            "See [project_data](https://x/y) for more",
            "See [Project Data](https://x/y) for more",
            "See [sources]( https://x/y) and [docs](unclosed",
            "[docs](u)",
            "[docs]()",
            "First\n[docs](u) second",
            "A name link [docs](u), twice [data](v).",
        ],
    )
    def test_keeps_a_name_that_is_the_text_of_a_markdown_link(self, text: str):
        """
        GIVEN a bracket that is an internal name and is immediately followed by a parenthesis
        WHEN the citations are removed
        THEN the bracket stays in the text with its link, whatever the link holds
        """
        assert remove_citations(text, SOURCES) == text

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("See [docs] (https://x/y) for more", "See (https://x/y) for more"),
            ("See [docs]\n(https://x/y)", "See\n(https://x/y)"),
            ("See [docs]", "See"),
            ("See [docs]   ", "See   "),
            ("See [docs], then [data].", "See, then."),
            ("See [docs][data](u)", "See[data](u)"),
            ("See [docs][1](u) now", "See now"),
            ("See [1](u)[docs](v)", "See[docs](v)"),
            ("See [[docs]x] and [[docs]data](u)", "See [x] and [data](u)"),
            ("[docs]", ""),
        ],
    )
    def test_removes_a_name_that_is_not_directly_followed_by_a_parenthesis(
        self, text: str, expected: str
    ):
        """
        GIVEN an internal name followed by a blank, a bracket, other text or the end
        WHEN the citations are removed
        THEN it goes as before, and a numbered citation still takes its link target with it
        """
        assert remove_citations(text, SOURCES) == expected

    def test_removes_the_tags_a_recorded_answer_cites(self):
        """
        GIVEN answers recorded from an evaluation run, which cite [project_data] and [1]
        WHEN the citations are removed
        THEN each reads as the same text without them
        """
        assert remove_citations(_RECORDED_EN, {1}) == _RECORDED_EN_CLEAN
        assert remove_citations(_RECORDED_CS, {1}) == _RECORDED_CS_CLEAN

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
        alphabet = [
            *["[", "]", "\u3010", "\u3011", "1", "2", "7", " ", ",", "-", "(", ")", "x", "\n"],
            *["docs", "data", "project_data", "\u00a0"],
        ]
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

    @pytest.mark.parametrize(
        ("answer", "clean"),
        [(_RECORDED_EN, _RECORDED_EN_CLEAN), (_RECORDED_CS, _RECORDED_CS_CLEAN)],
    )
    def test_a_recorded_answer_cut_anywhere_joins_to_the_cleaned_answer(
        self, answer: str, clean: str
    ):
        """
        GIVEN an answer recorded from an evaluation run, which cites [project_data] and [1]
        WHEN it is cut in two at every index, and again fed one character at a time
        THEN the text let out is always the start of the cleaned answer and joins to it
        """
        for index in range(len(answer) + 1):
            self._assert_exact(answer, [answer[:index], answer[index:]])
        self._assert_exact(answer, list(answer))
        assert remove_citations(answer, SOURCES) == clean

    def test_a_closed_name_is_held_back_until_the_next_character_decides_it(self):
        """
        GIVEN a stream that has just read an internal name in brackets
        WHEN a parenthesis arrives, and in another run any other character, or the end
        THEN only the text before its blank is let out first; a parenthesis then lets the
             bracket out with its link, anything else or the end removes it
        """
        link = CitationStreamFilter(SOURCES)
        assert link.feed("See [docs]") == "See"
        assert link.feed("(") == " [docs]("
        assert link.feed("u)") + link.finish() == "u)"

        gone = CitationStreamFilter(SOURCES)
        assert gone.feed("See [docs]") == "See"
        assert gone.feed(" x") + gone.finish() == " x"

        end = CitationStreamFilter(SOURCES)
        assert end.feed("See [docs]") == "See"
        assert end.finish() == ""

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

    @pytest.mark.parametrize(
        ("answer", "expected"),
        [
            ("[1] The midpoint is here.", "The midpoint is here."),
            ("[1]   The midpoint is here.", "The midpoint is here."),
            ("Intro.\n[1] The midpoint is here.", "Intro.\nThe midpoint is here."),
            ("  [1] The midpoint is here.", "  The midpoint is here."),
        ],
    )
    def test_the_words_after_a_citation_that_opens_a_line_keep_their_spaces(
        self, answer: str, expected: str
    ):
        """
        GIVEN a citation at the start of a line followed by several words
        WHEN the answer is fed in one piece, and again one character at a time
        THEN the blanks right after the citation go and the spaces between the words stay
        """
        one_shot = CitationStreamFilter(SOURCES)
        by_character = CitationStreamFilter(SOURCES)

        assert one_shot.feed(answer) + one_shot.finish() == expected
        assert "".join(by_character.feed(char) for char in answer) + by_character.finish() == (
            expected
        )

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
