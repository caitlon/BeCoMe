"""Tests for how the report arranges what it shows.

The page does not present its three figures as equals: the compromise is the
answer, and the mean and median are how it was reached. A report that lists all
three as identical table rows tells the reader nothing about which is which.
"""

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
from tests.shared.pdf_inspection import as_fractions, fill_colours


def _data(agreement: AgreementLevel = AgreementLevel.HIGH) -> ResultExportData:
    """Build a result carrying a given agreement reading."""
    return ResultExportData(
        project_name="Flood prevention",
        project_description=None,
        scale_min=0.0,
        scale_max=100.0,
        scale_unit="%",
        generated_at=datetime(2026, 9, 9, tzinfo=UTC),
        num_experts=13,
        max_error=5.97,
        best_compromise=FuzzyTriple(11.54, 14.19, 17.19),
        arithmetic_mean=FuzzyTriple(10.0, 13.0, 16.0),
        median=FuzzyTriple(12.0, 15.0, 18.0),
        agreement=agreement,
        likert_value=None,
        likert_decision=None,
        opinions=(OpinionRow("Jan Novak", "Head", 10.0, 14.0, 18.0),),
    )


class TestAgreementBadge:
    """The verdict is shown in colour, as the page shows it."""

    @pytest.mark.parametrize(
        ("agreement", "field"),
        [
            (AgreementLevel.HIGH, "agreement_high"),
            (AgreementLevel.MODERATE, "agreement_moderate"),
            (AgreementLevel.LOW, "agreement_low"),
        ],
    )
    def test_the_badge_carries_the_colour_of_its_level(self, agreement: AgreementLevel, field: str):
        """Each level paints its badge in that level's token.

        A reader who only glances at the report should get the verdict from the
        colour, which is exactly what the badge on the page is for.
        """
        # GIVEN a result read at one agreement level
        palette = get_palette(ReportTheme.LIGHT)

        # WHEN the report is rendered
        content = PdfResultRenderer(palette).render(_data(agreement), get_labels(ReportLang.EN))

        # THEN that level's colour is painted somewhere in the document
        assert as_fractions(getattr(palette, field)) in fill_colours(content)

    def test_a_high_reading_does_not_paint_the_low_colour(self):
        """The badge shows one verdict, not all three."""
        # GIVEN a result with high agreement
        palette = get_palette(ReportTheme.LIGHT)

        # WHEN it is rendered
        content = PdfResultRenderer(palette).render(
            _data(AgreementLevel.HIGH), get_labels(ReportLang.EN)
        )

        # THEN the colour reserved for low agreement is absent
        assert as_fractions(palette.agreement_low) not in fill_colours(content)
