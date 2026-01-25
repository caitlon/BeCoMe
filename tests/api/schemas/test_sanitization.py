"""Tests for HTML sanitization utilities."""

from api.schemas.sanitization import sanitize_text, sanitize_text_or_none


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


class TestSanitizeTextOrNone:
    """Tests for sanitize_text_or_none function."""

    def test_none_returns_none(self):
        """
        GIVEN None value
        WHEN sanitize_text_or_none is called
        THEN None is returned
        """
        # WHEN
        result = sanitize_text_or_none(None)

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
