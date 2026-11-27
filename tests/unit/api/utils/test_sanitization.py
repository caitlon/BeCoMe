"""Tests for HTML sanitization utilities."""

import pytest

from api.utils.sanitization import sanitize_text, sanitize_text_or_none


class TestSanitizeText:
    """Tests for sanitize_text function."""

    def test_removes_html_tags(self):
        """
        GIVEN text containing HTML tags
        WHEN sanitize_text is called
        THEN HTML tags are removed and text content is preserved
        """
        # GIVEN
        text_with_html = "<script>alert('xss')</script>Hello <b>World</b>"

        # WHEN
        result = sanitize_text(text_with_html)

        # THEN
        assert result == "alert('xss')Hello World"

    def test_empty_string_returns_empty(self):
        """
        GIVEN an empty string
        WHEN sanitize_text is called
        THEN empty string is returned
        """
        # GIVEN
        empty = ""

        # WHEN
        result = sanitize_text(empty)

        # THEN
        assert result == ""

    def test_plain_text_unchanged(self):
        """
        GIVEN plain text without HTML
        WHEN sanitize_text is called
        THEN text is returned unchanged
        """
        # GIVEN
        plain_text = "Hello World"

        # WHEN
        result = sanitize_text(plain_text)

        # THEN
        assert result == "Hello World"


class TestSanitizeTextInvisibleCharacters:
    """Tests for the removal of characters that render as nothing."""

    @pytest.mark.parametrize("invisible", ["\u202e", "\u200b", "\u00ad"])
    def test_invisible_characters_removed(self, invisible):
        """
        GIVEN text holding a bidirectional override, a zero-width space or a soft hyphen
        WHEN sanitize_text is called
        THEN the character is removed
        """
        # WHEN
        result = sanitize_text(f"14{invisible}.19")

        # THEN
        assert result == "14.19"

    def test_invisible_character_cannot_hide_a_tag(self):
        """
        GIVEN a tag whose name is split by a zero-width space
        WHEN sanitize_text is called
        THEN the tag is stripped like any other
        """
        # WHEN
        result = sanitize_text("<scr\u200bipt>x</script>")

        # THEN
        assert result == "x"

    def test_line_break_and_tab_kept_and_carriage_returns_normalised(self):
        """
        GIVEN text with a newline, a tab, a Windows line break and a lone carriage return
        WHEN sanitize_text is called
        THEN the newline and tab stay and the others become newlines
        """
        # WHEN
        result = sanitize_text("a\n\tb\r\nc\rd")

        # THEN
        assert result == "a\n\tb\nc\nd"


class TestSanitizeTextOrNone:
    """Tests for sanitize_text_or_none function."""

    def test_none_returns_none(self):
        """
        GIVEN None value
        WHEN sanitize_text_or_none is called
        THEN None is returned
        """
        # GIVEN
        value = None

        # WHEN
        result = sanitize_text_or_none(value)

        # THEN
        assert result is None

    def test_html_is_sanitized(self):
        """
        GIVEN text with HTML tags
        WHEN sanitize_text_or_none is called
        THEN HTML is removed
        """
        # GIVEN
        text_with_html = "<div>Content</div>"

        # WHEN
        result = sanitize_text_or_none(text_with_html)

        # THEN
        assert result == "Content"
