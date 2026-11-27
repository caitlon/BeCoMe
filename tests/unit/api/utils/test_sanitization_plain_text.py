"""Tests that sanitize_text stores plain text: tags stripped, ``&``, ``<`` and ``>`` kept."""

import html

import bleach
import pytest
from hypothesis import given, reject
from hypothesis import strategies as st

from api.utils.invisible import strip_invisible
from api.utils.sanitization import sanitize_text, sanitize_text_or_none

_FRAGMENTS = [
    "<b>",
    "</b>",
    "<!--",
    "-->",
    "<![CDATA[",
    "]]>",
    "&lt;",
    "&amp;",
    "&#60;",
    "&#x200b;",
    "\u200b",
    "\r\n",
]
_TEXT = st.lists(
    st.one_of(
        st.sampled_from(_FRAGMENTS),
        st.text(alphabet="<>&;#/!-ab c\u200b\r\n", max_size=6),
    ),
    max_size=12,
).map("".join)


def _sanitize_or_reject(text: str) -> str:
    """Sanitize generated text, rejecting the example when the pass limit refuses it.

    Tags nested five or more levels deep are refused by design (``TestPassLimit``). The
    strategy rarely builds them, but such an example says nothing about the properties
    below. Any other ValueError still fails the test.
    """
    try:
        return sanitize_text(text)
    except ValueError as exc:
        if "could not be sanitized" not in str(exc):
            raise
        reject()


class TestSpecialCharactersKept:
    """``&``, ``<`` and ``>`` stay as typed."""

    @pytest.mark.parametrize("text", ["R&D", "a<b", "5 < 6 > 4", "x>y", "AT&T", "<", ">", "&"])
    def test_characters_are_not_escaped(self, text):
        """
        GIVEN text with a bare ampersand or angle bracket and no tag
        WHEN sanitize_text is called
        THEN the text comes back unchanged
        """
        # WHEN
        result = sanitize_text(text)

        # THEN
        assert result == text

    @pytest.mark.parametrize("char", ["&", "<", ">"])
    def test_result_is_not_longer_than_input(self, char):
        """
        GIVEN 255 copies of a special character
        WHEN sanitize_text is called
        THEN all 255 come back
        """
        # WHEN
        result = sanitize_text(char * 255)

        # THEN
        assert result == char * 255


class TestTagsStillStripped:
    """Markup is removed, including markup that only appears after a first strip."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("<b>bold</b>", "bold"),
            ("<scr<b>ipt>x", "ipt>x"),
            ("<<b>b>", ""),
            ("<<b>script>alert(1)", "alert(1)"),
            ("a<!-- hidden -->b", "ab"),
            ("a<![CDATA[hidden]]>b", "ab"),
            ("R&D <i>team</i>", "R&D team"),
        ],
    )
    def test_tags_comments_and_cdata_removed(self, text, expected):
        """
        GIVEN text with tags, nested tags, a comment or a CDATA section
        WHEN sanitize_text is called
        THEN none of the markup is left
        """
        # WHEN
        result = sanitize_text(text)

        # THEN
        assert result == expected


class TestTypedEntitiesStayLiteral:
    """An entity the user typed is text, not a character to decode."""

    @pytest.mark.parametrize("text", ["R&amp;D", "&lt;b&gt;", "&#60;", "&#x200b;", "&amp;amp;"])
    def test_entities_are_kept_as_typed(self, text):
        """
        GIVEN text that spells an HTML entity
        WHEN sanitize_text is called
        THEN the entity stays as the same characters and is not decoded
        """
        # WHEN
        result = sanitize_text(text)

        # THEN
        assert result == text

    def test_entity_for_an_invisible_character_is_not_decoded(self):
        """
        GIVEN the entity for a zero-width space
        WHEN sanitize_text is called
        THEN no invisible character appears in the result
        """
        # WHEN
        result = sanitize_text("a&#x200b;b")

        # THEN
        assert strip_invisible(result) == result


class TestOtherBehaviourKept:
    """Invisible characters and line breaks are handled as before."""

    def test_line_breaks_normalised(self):
        """
        GIVEN text with a Windows line break and a lone carriage return
        WHEN sanitize_text is called
        THEN both become a newline
        """
        # WHEN
        result = sanitize_text("a\r\nb\rc")

        # THEN
        assert result == "a\nb\nc"

    def test_invisible_character_removed_next_to_a_special_character(self):
        """
        GIVEN a zero-width space between an ampersand and a letter
        WHEN sanitize_text is called
        THEN the space is removed and the ampersand stays
        """
        # WHEN
        result = sanitize_text("R&\u200bD")

        # THEN
        assert result == "R&D"

    @pytest.mark.parametrize("text", ["R&D", "<scr<b>ipt>x", "<<b>b>", "R&amp;D", "a<b"])
    def test_sanitizing_twice_changes_nothing(self, text):
        """
        GIVEN text that has been sanitized once
        WHEN it is sanitized again
        THEN it comes back unchanged
        """
        # GIVEN
        once = sanitize_text(text)

        # WHEN
        twice = sanitize_text(once)

        # THEN
        assert twice == once


class TestPassLimit:
    """Input that needs more cleaning passes than the limit is refused."""

    def test_tags_nested_four_deep_are_stripped(self):
        """
        GIVEN tags nested four levels deep
        WHEN sanitize_text is called
        THEN nothing is left
        """
        # WHEN
        result = sanitize_text("<" * 4 + "b>" * 4)

        # THEN
        assert result == ""

    def test_tags_nested_five_deep_are_refused(self):
        """
        GIVEN tags nested five levels deep
        WHEN sanitize_text is called
        THEN ValueError is raised with a neutral message
        """
        # WHEN / THEN
        with pytest.raises(ValueError, match="could not be sanitized"):
            sanitize_text("<" * 5 + "b>" * 5)


class TestNoneVariant:
    """sanitize_text_or_none passes None through."""

    def test_none_stays_none(self):
        """
        GIVEN None
        WHEN sanitize_text_or_none is called
        THEN None is returned
        """
        # WHEN / THEN
        assert sanitize_text_or_none(None) is None


class TestSanitizedTextProperties:
    """Properties that hold for any input."""

    @given(_TEXT)
    def test_oracle_matches_bleach_on_escaped_text(self, text):
        """
        GIVEN any text
        WHEN it is sanitized
        THEN bleach finds nothing left to strip in the result, and the result never grew
        """
        # WHEN
        result = _sanitize_or_reject(text)

        # THEN
        escaped = bleach.clean(result.replace("&", "&amp;"), tags=[], strip=True)
        assert escaped == html.escape(result, quote=False)
        assert len(result) <= len(text)

    @given(_TEXT)
    def test_result_is_a_fixed_point_without_invisible_characters(self, text):
        """
        GIVEN any text
        WHEN it is sanitized
        THEN sanitizing the result changes nothing and no invisible character is left
        """
        # WHEN
        result = _sanitize_or_reject(text)

        # THEN
        assert sanitize_text(result) == result
        assert strip_invisible(result) == result
