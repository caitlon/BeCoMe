"""Tests for the removal of characters that render as nothing."""

import sys
import unicodedata

import pytest

from api.assistant.invisible import strip_invisible

# Formatting characters (category Cf) a text may carry: the soft hyphen, zero-width space,
# non-joiner and joiner, the direction marks, the embeddings and overrides, the word joiner,
# the isolates, the byte order mark, the Arabic letter mark, the Mongolian vowel separator and
# two tag characters.
_KNOWN_CF = [
    0x00AD,
    0x200B,
    0x200C,
    0x200D,
    0x200E,
    0x200F,
    *range(0x202A, 0x202F),
    0x2060,
    *range(0x2066, 0x206A),
    0xFEFF,
    0x061C,
    0x180E,
    0xE0001,
    0xE0041,
]

# The characters that are not Cc or Cf and still draw nothing.
_EXTRAS = [
    0x034F,
    0x115F,
    0x1160,
    0x17B4,
    0x17B5,
    0x180B,
    0x180C,
    0x180D,
    0x180F,
    0x2065,
    0x3164,
    *range(0xFE00, 0xFE10),
    0xFFA0,
    *range(0xFFF0, 0xFFF9),
    *range(0xE0100, 0xE01F0),
    0xE0000,
    0xE0FFF,
]


class TestLineBreaksAndTabs:
    """Line breaks are normalised to a newline, and the newline and the tab stay."""

    def test_newline_and_tab_survive(self):
        """
        GIVEN text with a newline and a tab
        WHEN invisible characters are stripped
        THEN both are still there
        """
        assert strip_invisible("a\tb\nc") == "a\tb\nc"

    def test_a_carriage_return_and_line_feed_become_one_newline(self):
        """
        GIVEN text with a Windows line break
        WHEN invisible characters are stripped
        THEN it is one newline
        """
        assert strip_invisible("a\r\nb") == "a\nb"

    def test_a_lone_carriage_return_becomes_a_newline(self):
        """
        GIVEN text with a lone carriage return, one in a row of two and one at the end
        WHEN invisible characters are stripped
        THEN each is a newline
        """
        assert strip_invisible("a\rb\r\rc\r") == "a\nb\n\nc\n"


class TestControlCharacters:
    """A control character is a space when Python calls it whitespace, and gone otherwise."""

    @pytest.mark.parametrize("char", ["\v", "\f", "\x1c", "\x1d", "\x1e", "\x1f", "\x85"])
    def test_a_whitespace_control_becomes_a_space(self, char):
        """
        GIVEN a whitespace control character between two words
        WHEN invisible characters are stripped
        THEN the words are separated by one space
        """
        assert strip_invisible(f"one{char}two") == "one two"

    @pytest.mark.parametrize("char", ["\x00", "\x07", "\x08", "\x1b", "\x7f", "\x80", "\x9f"])
    def test_any_other_control_is_removed(self, char):
        """
        GIVEN a control character inside a word
        WHEN invisible characters are stripped
        THEN it is gone and the word is whole
        """
        assert strip_invisible(f"one{char}two") == "onetwo"


class TestFormattingCharacters:
    """Formatting characters and the listed extras are removed."""

    @pytest.mark.parametrize("code", _KNOWN_CF, ids=lambda code: f"U+{code:04X}")
    def test_a_known_formatting_character_is_removed(self, code):
        """
        GIVEN a known formatting character between two letters
        WHEN invisible characters are stripped
        THEN it is gone
        """
        assert unicodedata.category(chr(code)) == "Cf"
        assert strip_invisible(f"a{chr(code)}b") == "ab"

    @pytest.mark.parametrize("code", _EXTRAS, ids=lambda code: f"U+{code:04X}")
    def test_an_extra_invisible_character_is_removed(self, code):
        """
        GIVEN a combining joiner, a Hangul filler or a variation selector between two letters
        WHEN invisible characters are stripped
        THEN it is gone
        """
        assert strip_invisible(f"a{chr(code)}b") == "ab"

    def test_no_character_the_runtime_calls_formatting_survives(self):
        """
        GIVEN every code point of Unicode category Cf the runtime knows
        WHEN they are stripped
        THEN nothing is left
        """
        everything = [
            chr(code)
            for code in range(sys.maxunicode + 1)
            if unicodedata.category(chr(code)) == "Cf"
        ]
        assert len(everything) > 100

        assert strip_invisible("".join(everything)) == ""


class TestVisibleSpaceStays:
    """The separators and the braille blank are drawn as space, so they are kept."""

    @pytest.mark.parametrize("char", ["\u2028", "\u2029", "\u2800"])
    def test_is_unchanged(self, char):
        """
        GIVEN a line separator, a paragraph separator or the braille blank between two words
        WHEN invisible characters are stripped
        THEN it is still there
        """
        assert strip_invisible(f"one{char}two") == f"one{char}two"


class TestVisibleText:
    """Text a reader can see is returned as it is."""

    @pytest.mark.parametrize(
        "text",
        [
            "Plain ASCII, with digits 14.19 and punctuation!",
            "Příliš žluťoučký kůň úpěl ďábelské ódy",
            "Done \U0001f600 \U0001f44d",
            "",
        ],
    )
    def test_is_unchanged(self, text):
        """
        GIVEN visible text: ASCII, Czech diacritics, emoji without joiners, nothing
        WHEN invisible characters are stripped
        THEN it is returned unchanged
        """
        assert strip_invisible(text) == text

    def test_non_ascii_letters_stay_and_only_the_invisible_ones_go(self):
        """
        GIVEN Czech text with a zero-width space and a bidi override inside it
        WHEN invisible characters are stripped
        THEN every letter is kept and the two are removed
        """
        assert strip_invisible(
            "P\u0159\u00ed\u200bli\u0161 \u017elu\u202e\u0165ou\u010dk\u00fd"
        ) == ("P\u0159\u00edli\u0161 \u017elu\u0165ou\u010dk\u00fd")
