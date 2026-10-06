"""Unit tests for the server-sent-event formatter."""

import json

from api.assistant.sse import format_event


class TestFormatEvent:
    """One event is a name line, one data line of JSON and a blank line."""

    def test_the_event_has_a_name_a_data_line_and_a_blank_line(self):
        """
        GIVEN an event name and a payload
        WHEN it is formatted
        THEN the text is the event line, the data line with compact JSON, and a blank line
        """
        # WHEN
        text = format_event("token", {"text": "Hi"})

        # THEN
        assert text == 'event: token\ndata: {"text":"Hi"}\n\n'

    def test_a_newline_inside_a_string_stays_on_one_data_line(self):
        """
        GIVEN a payload whose string holds a newline and a blank line
        WHEN it is formatted
        THEN the data is a single line, so only the final blank line ends the event
        """
        # WHEN
        text = format_event("token", {"text": "one\n\ntwo"})

        # THEN
        lines = text.split("\n")
        assert len([line for line in lines if line.startswith("data: ")]) == 1
        assert text.count("\n\n") == 1
        assert json.loads(lines[1][len("data: ") :]) == {"text": "one\n\ntwo"}

    def test_non_ascii_text_is_kept_as_written(self):
        """
        GIVEN a Czech payload
        WHEN it is formatted
        THEN the letters are in the text and not as \\u escapes
        """
        # WHEN
        text = format_event("token", {"text": "Příliš žluťoučký kůň"})

        # THEN
        assert "Příliš žluťoučký kůň" in text
        assert "\\u" not in text

    def test_the_unicode_line_separators_are_escaped(self):
        """
        GIVEN a payload whose string holds U+2028, U+2029 and U+0085
        WHEN it is formatted
        THEN the text stays on one data line, because those three are line breaks to some
            parsers, and the data still parses back to the same string
        """
        # GIVEN
        text = "a\u2028b\u2029c\u0085d"

        # WHEN
        framed = format_event("token", {"text": text})

        # THEN
        # str.splitlines breaks on all three, as httpx's aiter_lines does
        name_line, data_line, blank_line = framed.splitlines()
        assert name_line == "event: token"
        assert blank_line == ""
        assert json.loads(data_line[len("data: ") :]) == {"text": text}
