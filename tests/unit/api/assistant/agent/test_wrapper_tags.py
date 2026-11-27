"""Tests for removing the assistant's wrapper tags from an answer, whole and piece by piece."""

import random
import time

import pytest

from api.assistant.agent.wrapper_tags import WrapperTagStreamFilter, remove_wrapper_tags
from tests.shared.assistant_fakes import WRAPPER_TAG_PATTERN

_REMOVED = [
    ("<docs>", ""),
    ("</docs>", ""),
    ("<docs/>", ""),
    ("<project_data>", ""),
    ("</project_data>", ""),
    ("<project_data/>", ""),
    ("<earlier_answer>", ""),
    ("</earlier_answer>", ""),
    ("<earlier_answer/>", ""),
    ("< docs >", ""),
    ("</ docs>", ""),
    ("< / docs >", ""),
    ("<docs />", ""),
    ("</docs/>", ""),
    ("<\tdocs\t>", ""),
    ("<DOCS>", ""),
    ("<Project_Data>", ""),
    ("<project-data>", ""),
    ("</Earlier-Answer>", ""),
    ("<docs" + " " * 300 + ">", ""),
    ("The <docs>midpoint</docs> is 14.", "The midpoint is 14."),
    ("<docs>The midpoint is 14.</docs>", "The midpoint is 14."),
]

_LINES = [
    ("<docs>\nbody\n</docs>\n", "body\n"),
    ("<docs>\nbody\n</docs>", "body\n"),
    ("a\n  <docs>  \nb", "a\nb"),
    ("a\n<docs>\n\nb", "a\n\nb"),
    ("x\n<docs>", "x\n"),
    ("\n<docs>\n", "\n"),
    ("<docs><project_data>\nx", "x"),
    ("a\n  \nb", "a\n  \nb"),
    ("text<docs>", "text"),
    ("x <docs>\ny", "x \ny"),
    ("a<docs></docs>b", "ab"),
    ("a<docs></docs> b", "a b"),
    ("slovo<docs>, dalsi", "slovo, dalsi"),
    ("is<docs>x", "isx"),
]

_STAY = [
    "<doc>",
    "<docs2>",
    "<documents>",
    "<project data>",
    '<docs source="x">',
    "<h2>",
    "a < docs and b > c",
    "a < b and c > d",
    "<docs",
    "<docs\n>",
    "<\ndocs>",
    "<d ocs>",
    "<docs//>",
    "<//docs>",
    "<docs x>",
    "x < 5",
    "a<b>",
    "<",
    ">",
    "</",
    "<>",
    "< >",
    "a<docs",
    "<!-- note -->",
    "<docs" + " " * 300,
    "<docs" + " " * 300 + "x>",
    "<" * 40 + "docs",
]

_RECOMBINED = [
    ("<<docs>docs>", ""),
    ("<docs<docs>>", ""),
    ("< <docs>docs>", ""),
    ("</<docs>docs>", ""),
    ("<do<docs>cs>", ""),
    ("<project_<docs>data>", ""),
    ("a<<docs>docs>b", "ab"),
    ("<<<docs>docs>docs>", ""),
    ("<do<x>cs>", "<do<x>cs>"),
]

_RECORDED = [
    (
        "<project_data>\nProject: Flood Prevention\nBest compromise: 14.19\n</project_data>\n\n"
        "The midpoint is 14.19.",
        "Project: Flood Prevention\nBest compromise: 14.19\n\nThe midpoint is 14.19.",
    ),
    (
        "<docs>\n[1] Method - Step 3\n<!-- hidden note -->\nThe midpoint.\n</docs>\nDone.",
        "[1] Method - Step 3\n<!-- hidden note -->\nThe midpoint.\nDone.",
    ),
    (
        "<earlier_answer>\nThe midpoint was 14.\n</earlier_answer>\nNow 15.",
        "The midpoint was 14.\nNow 15.",
    ),
    (
        "I cannot repeat <project_data>, <docs> or <earlier_answer> text.",
        "I cannot repeat ,  or  text.",
    ),
    ("Print `<docs>` as code.", "Print `` as code."),
    ("```\n<docs>\nx\n</docs>\n```", "```\nx\n```"),
]

_CASES = [text for text, _ in [*_REMOVED, *_LINES, *_RECOMBINED, *_RECORDED]] + _STAY

_FUZZ_ALPHABET = [
    *["<", ">", "/", " ", "\t", "\n", "a", "x"],
    *["do", "cs", "docs", "project", "_data", "earlier", "_answer", "-", "D"],
]


class TestRemoveWrapperTags:
    """A wrapper tag goes alone; the text around it stays."""

    @pytest.mark.parametrize(("text", "expected"), _REMOVED)
    def test_a_tag_goes_in_each_of_its_spellings(self, text: str, expected: str):
        """
        GIVEN a tag that is opening, closing or self-closing, with blanks, in any case, or
              with a hyphen for the underscore
        WHEN the wrapper tags are removed
        THEN the tag is gone and the text around it stays
        """
        assert remove_wrapper_tags(text) == expected

    @pytest.mark.parametrize(("text", "expected"), _LINES)
    def test_a_line_that_held_only_tags_goes_with_its_line_break(self, text: str, expected: str):
        """
        GIVEN tags on lines of their own, next to tags in a line of text
        WHEN the wrapper tags are removed
        THEN a line that is left with only blanks goes whole, a line of text keeps its blanks,
             and nothing is put in the place of a tag
        """
        assert remove_wrapper_tags(text) == expected

    @pytest.mark.parametrize("text", _STAY)
    def test_text_that_is_not_a_tag_stays_exactly(self, text: str):
        """
        GIVEN text that only looks like a tag, or is broken by a line break
        WHEN the wrapper tags are removed
        THEN it is returned unchanged
        """
        assert remove_wrapper_tags(text) == text

    @pytest.mark.parametrize(("text", "expected"), _RECOMBINED)
    def test_a_tag_that_removal_would_assemble_goes_too(self, text: str, expected: str):
        """
        GIVEN a tag with another tag inside it, so that removing the inner one leaves the
              outer one whole
        WHEN the wrapper tags are removed
        THEN the outer one is removed as well, so no tag is left
        """
        assert remove_wrapper_tags(text) == expected

    @pytest.mark.parametrize(("text", "expected"), _RECORDED)
    def test_the_shapes_models_wrote_lose_their_tags_and_keep_their_text(
        self, text: str, expected: str
    ):
        """
        GIVEN an answer that prints the project block, the excerpts, an earlier answer, a
              sentence that names the tags, or a tag inside code
        WHEN the wrapper tags are removed
        THEN the tags are gone wherever they stand and the other markup stays
        """
        assert remove_wrapper_tags(text) == expected

    @pytest.mark.parametrize("text", _CASES)
    def test_removing_again_changes_nothing(self, text: str):
        """
        GIVEN the result of removing the wrapper tags from a text
        WHEN they are removed again
        THEN the text is the same
        """
        once = remove_wrapper_tags(text)

        assert remove_wrapper_tags(once) == once

    def test_random_texts_hold_no_tag_afterwards_and_are_stable(self):
        """
        GIVEN random texts made of angle brackets, slashes, blanks, line breaks and the
              fragments of the tag names
        WHEN the wrapper tags are removed
        THEN no tag is left, and removing again changes nothing
        """
        rng = random.Random(11)
        for _ in range(4000):
            text = "".join(rng.choice(_FUZZ_ALPHABET) for _ in range(rng.randint(0, 24)))
            once = remove_wrapper_tags(text)
            assert WRAPPER_TAG_PATTERN.search(once) is None, text
            assert remove_wrapper_tags(once) == once, text

    def test_the_text_between_the_tags_is_never_lost(self):
        """
        GIVEN random texts of letters with tags put between them
        WHEN the wrapper tags are removed
        THEN the letters come back in order
        """
        rng = random.Random(5)
        tags = ["<docs>", "</docs>", "<project_data>", "< / earlier-answer >", "<docs/>"]
        for _ in range(500):
            words = [rng.choice(["a", "bc", "x1"]) for _ in range(rng.randint(1, 8))]
            text = "".join(w + rng.choice(["", *tags]) for w in words)
            assert remove_wrapper_tags(text) == "".join(words), text


class TestWrapperTagStreamFilter:
    """The pieces let out join to the cleaned text and are never revised."""

    @staticmethod
    def _assert_exact(text: str, pieces: list[str]) -> None:
        expected = remove_wrapper_tags(text)
        stream = WrapperTagStreamFilter()
        joined = ""
        for piece in pieces:
            joined += stream.feed(piece)
            # What is let out is the start of the final text, so nothing is ever taken back.
            assert expected.startswith(joined), (pieces, joined)
        joined += stream.finish()
        assert joined == expected, pieces

    @pytest.mark.parametrize("text", _CASES)
    def test_every_split_in_two_adds_up_to_the_cleaned_text(self, text: str):
        """
        GIVEN a text and every index at which it can be cut in two
        WHEN the two pieces are fed through the filter
        THEN the text let out is at every moment the start of the cleaned text, and joins to it
        """
        for index in range(len(text) + 1):
            self._assert_exact(text, [text[:index], text[index:]])

    @pytest.mark.parametrize("text", _CASES)
    def test_one_character_pieces_add_up_to_the_cleaned_text(self, text: str):
        """
        GIVEN a text arriving one character at a time
        WHEN it is fed through the filter
        THEN the text let out joins to the cleaned text
        """
        self._assert_exact(text, list(text))

    def test_a_tag_cut_inside_its_name_is_never_shown_in_part(self):
        """
        GIVEN a tag cut in the middle of its name
        WHEN the pieces are fed through the filter
        THEN nothing of the tag is let out, and the text around it is
        """
        stream = WrapperTagStreamFilter()

        shown = [
            stream.feed("Before <do"),
            stream.feed("cs>After </pro"),
            stream.feed("ject_data>"),
        ]

        assert shown == ["Before ", "After ", ""]
        assert stream.finish() == ""

    def test_text_that_cannot_become_a_tag_is_let_out_at_once(self):
        """
        GIVEN a less-than sign followed by a character that no tag has
        WHEN the piece is fed through the filter
        THEN the text is let out without waiting for the end of the answer
        """
        stream = WrapperTagStreamFilter()

        assert stream.feed("If x < 5 then") == "If x < 5 then"

    def test_a_less_than_sign_that_cannot_start_a_tag_lets_go_of_the_ones_before_it(self):
        """
        GIVEN two less-than signs in a row and then text that no tag has
        WHEN the piece is fed through the filter
        THEN everything is let out at once, as a closing sign is read against the last one
        """
        stream = WrapperTagStreamFilter()

        assert stream.feed("a << b and then text") == "a << b and then text"

    def test_a_possible_tag_is_held_until_it_is_settled(self):
        """
        GIVEN a piece that ends inside what may still become a tag
        WHEN it is fed through the filter and the answer ends
        THEN the part is held back, and let out whole at the end when it was no tag
        """
        stream = WrapperTagStreamFilter()

        assert stream.feed("see <doc") == "see "
        assert stream.finish() == "<doc"

    def test_a_line_that_may_still_turn_out_to_hold_only_tags_is_held(self):
        """
        GIVEN a line of blanks and one tag, with the line break to come
        WHEN the pieces are fed through the filter
        THEN the line is held until the line break, and goes whole with it
        """
        stream = WrapperTagStreamFilter()

        assert stream.feed("a\n  <docs>  ") == "a\n"
        assert stream.feed("\nb") == "b"

    def test_random_texts_are_independent_of_how_they_are_cut(self):
        """
        GIVEN random texts made of angle brackets, slashes, blanks, line breaks and the
              fragments of the tag names, each cut in random places
        WHEN they are fed to the stream filter
        THEN the pieces join to what the whole text gives
        """
        rng = random.Random(7)
        for _ in range(3000):
            text = "".join(rng.choice(_FUZZ_ALPHABET) for _ in range(rng.randint(0, 24)))
            cuts = sorted(rng.randint(0, len(text)) for _ in range(rng.randint(0, 4)))
            pieces = [text[a:b] for a, b in zip([0, *cuts], [*cuts, len(text)], strict=True)]
            self._assert_exact(text, pieces)

    def test_a_long_run_of_blanks_after_an_angle_bracket_costs_no_more_than_its_length(self):
        """
        GIVEN a less-than sign and name, then thousands of pieces of blanks
        WHEN they are fed through the filter
        THEN it finishes in a small fraction of the time a rescan per piece takes (seconds),
             and the closing sign still removes the tag
        """
        stream = WrapperTagStreamFilter()
        started = time.perf_counter()

        shown = [stream.feed("<docs")]
        shown.extend(stream.feed(" " * 16) for _ in range(4000))
        shown.append(stream.feed(">end"))

        assert time.perf_counter() - started < 1.0
        assert "".join(shown) + stream.finish() == "end"

    def test_deeply_nested_angle_brackets_cost_no_more_than_their_length(self):
        """
        GIVEN tens of thousands of opening signs followed by as many closing ones
        WHEN they are removed
        THEN it finishes in a small fraction of the time a rescan per sign takes (seconds)
        """
        text = "<" * 30000 + "docs" + ">" * 30000
        started = time.perf_counter()

        result = remove_wrapper_tags(text)

        assert time.perf_counter() - started < 1.0
        assert result == "<" * 29999 + ">" * 29999
