"""Tests for the report's typefaces and their glyph coverage.

reportlab has no per-glyph fallback: a character the face lacks is drawn as
``.notdef`` with no exception and no log line, and every existing renderer test
would still pass. These tests are what turns that silence into a red build.
"""

from dataclasses import fields

import pytest
from reportlab.pdfbase import pdfmetrics

from api.services.export.data import ReportLang
from api.services.export.fonts import (
    FONT_DISPLAY,
    FONT_MONO,
    FONT_SANS,
    FONT_SANS_BOLD,
    font_for,
    register_fonts,
)
from api.services.export.labels import ResultLabels, get_labels


def _covers(face: str, text: str) -> list[str]:
    """Return the characters of ``text`` the face cannot draw."""
    register_fonts()
    coverage = pdfmetrics.getFont(face).face.charToGlyph
    return [char for char in text if ord(char) not in coverage]


class TestGlyphCoverage:
    """Every string the report can print must be printable."""

    @pytest.mark.parametrize("lang", list(ReportLang))
    @pytest.mark.parametrize("face", [FONT_SANS, FONT_SANS_BOLD])
    def test_every_report_label_is_drawable_in_the_text_face(self, lang: ReportLang, face: str):
        """No label loses a character to .notdef, in either language.

        Czech diacritics and the method's Γ, Ω and Δ all live in these strings.
        """
        # GIVEN the labels for one report language
        labels = get_labels(lang)

        # WHEN each of them is checked against the face that draws it
        # THEN none has a character the face cannot render
        for field in fields(ResultLabels):
            value = getattr(labels, field.name)
            texts = value.values() if isinstance(value, dict) else [value]
            for text in texts:
                missing = _covers(face, text)
                assert not missing, (
                    f"{lang.value} label {field.name!r} needs {''.join(missing)!r}, "
                    f"which {face} cannot draw"
                )

    def test_numbers_are_drawable_in_the_mono_face(self):
        """The digits and separators the report prints exist in JetBrains Mono."""
        # GIVEN / WHEN / THEN
        assert not _covers(FONT_MONO, "0123456789.,-±%")


class TestDisplayFaceFallback:
    """Playfair Display is used only where it can actually draw the string."""

    def test_greek_gamma_falls_back_to_the_text_face(self):
        """Playfair has Ω and Δ but no Γ, and the method's measures use Γ.

        Without the check reportlab would draw a blank box in the heading and say
        nothing about it.
        """
        # GIVEN a heading carrying the method's Gamma
        # WHEN the face is chosen
        # THEN the display face is declined in favour of one that can draw it
        assert font_for("Arithmetic Mean (Γ)", FONT_DISPLAY) == FONT_SANS

    def test_czech_heading_keeps_the_display_face(self):
        """Czech diacritics are covered, so a Czech title stays in Playfair."""
        # GIVEN / WHEN / THEN
        assert font_for("Protipovodňová opatření", FONT_DISPLAY) == FONT_DISPLAY

    def test_omega_and_delta_keep_the_display_face(self):
        """Only Gamma is missing; Ω and Δ must not trigger the fallback."""
        # GIVEN / WHEN / THEN
        assert font_for("Median (Ω), Δmax", FONT_DISPLAY) == FONT_DISPLAY
