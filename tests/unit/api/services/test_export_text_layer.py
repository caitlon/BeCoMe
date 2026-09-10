"""Tests that what the report draws can also be read back out of it.

Every other guard here works forward: the font has the glyph, the renderer picks
that font. This one works backward, from the finished document.

What it does catch: a character disappearing from the report entirely -- a bundled
face swapped for one with narrower coverage, a label rewritten with a symbol nobody
checked. reportlab draws those as `.notdef`, silently, with no exception and no log
line, and no forward-looking test notices.

What it does NOT catch, measured rather than assumed: removing the coverage check
from `font_for` leaves these tests green. Γ appears in the aggregates table as well
as in the heading, so it still reaches the text layer through Inter even when
Playfair is handed a string it cannot draw. That mutation is caught by
`TestDisplayFaceFallback` and `TestFallbackKeepsWeight` in test_export_fonts.py --
worth knowing, so this file is not mistaken for covering it.
"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from api.services.agreement_level import AgreementLevel
from api.services.export.data import (
    FuzzyTriple,
    OpinionRow,
    ReportLang,
    ResultExportData,
)
from api.services.export.labels import get_labels
from api.services.export.renderers import PdfResultRenderer
from api.services.export.theme import ReportTheme, get_palette
from tests.shared.pdf_inspection import embedded_fonts, text_characters

# The method's own notation, and the Czech letters most likely to be dropped by a
# face chosen for looks rather than coverage. Every letter here occurs in the
# fixture's own data, so the English report carries them too: they arrive from user
# text, not from the report's labels. A letter listed but absent from the data would
# make this test assert about a character the document never had reason to contain.
_METHOD_SYMBOLS = "ΓΩΔ"
_CZECH_LETTERS = "ňřížáéčš"


def _data() -> ResultExportData:
    """Build a result whose text exercises both alphabets the report can print."""
    return ResultExportData(
        project_name="Protipovodňová opatření",
        project_description="Rozpočet na hráze u Vltavy",
        scale_min=0.0,
        scale_max=100.0,
        scale_unit="%",
        generated_at=datetime(2026, 9, 10, tzinfo=UTC),
        num_experts=2,
        max_error=5.97,
        agreement=AgreementLevel.HIGH,
        best_compromise=FuzzyTriple(11.54, 14.19, 17.19),
        arithmetic_mean=FuzzyTriple(10.0, 13.0, 16.0),
        median=FuzzyTriple(12.0, 15.0, 18.0),
        likert_value=None,
        likert_decision=None,
        opinions=(
            OpinionRow("Šimon Novák", "šéf oddělení", 10.0, 14.0, 18.0),
            OpinionRow("Eva Dvořáková", "Hydroložka", 12.0, 15.0, 19.0),
        ),
    )


class TestTheTextLayerCarriesWhatWasDrawn:
    """A character in the document can be selected, searched and copied."""

    @pytest.mark.parametrize("lang", list(ReportLang))
    @pytest.mark.parametrize("theme", list(ReportTheme))
    def test_the_method_symbols_survive_into_the_document(
        self, lang: ReportLang, theme: ReportTheme
    ):
        """Γ, Ω and Δ are readable, not blank boxes that merely look drawn.

        These three are the report's most fragile characters: Playfair Display has
        Ω and Δ but not Γ. This asserts they are readable somewhere in the document,
        which is what fails if a face loses the range altogether; whether the right
        face was chosen for the heading is a different question, answered in
        test_export_fonts.py.
        """
        # GIVEN a report in one language and theme
        content = PdfResultRenderer(get_palette(theme)).render(_data(), get_labels(lang))

        # WHEN its text layer is read back
        characters = text_characters(content)

        # THEN each symbol of the method's notation is there
        missing = [symbol for symbol in _METHOD_SYMBOLS if symbol not in characters]
        assert not missing, f"{''.join(missing)} did not reach the text layer"

    @pytest.mark.parametrize("lang", list(ReportLang))
    def test_czech_letters_survive_into_the_document(self, lang: ReportLang):
        """Czech diacritics are readable in both languages.

        They arrive from user text -- a project name, an expert's name -- so they
        appear in the English report too whenever the data is Czech.
        """
        # GIVEN a report whose data carries Czech names
        content = PdfResultRenderer(get_palette(ReportTheme.LIGHT)).render(
            _data(), get_labels(lang)
        )

        # WHEN its text layer is read back
        characters = text_characters(content)

        # THEN none of the letters was lost
        missing = [letter for letter in _CZECH_LETTERS if letter not in characters]
        assert not missing, f"{''.join(missing)} did not reach the text layer"

    def test_a_character_no_face_can_draw_is_absent(self):
        """The guard has to be able to fail, so prove it on a character we lack.

        No bundled face has CJK, and this is what the failure looks like: the
        document renders, nothing raises, and the character simply is not there.
        That is the silence these tests exist to break.
        """
        # GIVEN a project named in a script none of the fonts covers
        data = replace(_data(), project_name="项目")

        # WHEN the report is rendered
        content = PdfResultRenderer(get_palette(ReportTheme.LIGHT)).render(
            data, get_labels(ReportLang.EN)
        )

        # THEN it is produced without complaint, and the characters are missing
        assert content.startswith(b"%PDF")
        characters = text_characters(content)
        assert "项" not in characters
        assert "Δ" in characters, "the rest of the document is unaffected"

    def test_the_document_embeds_only_the_report_faces(self):
        """Nothing but the three interface families draws text.

        Helvetica and Times-Roman appear in the resources because reportlab
        declares them on every canvas; measurement shows they draw nothing, so
        their presence is not asserted either way.
        """
        # GIVEN a rendered report
        content = PdfResultRenderer(get_palette(ReportTheme.LIGHT)).render(
            _data(), get_labels(ReportLang.EN)
        )

        # WHEN the embedded faces are listed
        families = {name.split("-")[0] for name in embedded_fonts(content)}

        # THEN the interface's three are there and the old stand-in is not
        assert {"Inter", "JetBrainsMono", "PlayfairDisplay"} <= families
        assert "DejaVuSans" not in families
