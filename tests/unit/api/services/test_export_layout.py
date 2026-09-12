"""Tests for how the report arranges what it shows.

The page does not present its three figures as equals: the compromise is the
answer, and the mean and median are how it was reached. A report that lists all
three as identical table rows tells the reader nothing about which is which.
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
from api.services.export.renderers import (
    _CARD_PADDING,
    _CONTENT_WIDTH,
    PdfResultRenderer,
)
from api.services.export.theme import ReportTheme, get_palette


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


def _find_badge(story) -> object | None:
    """Return the badge table from a rendered story, or None when it is absent.

    The badge is the one-cell table nested in the compromise card. Looking for it
    by structure is the point: an earlier version of these tests only asked whether
    the level's colour appeared anywhere in the finished PDF, and the Δmax bar
    paints that same colour -- so deleting the badge entirely left them green.
    """
    for flowable in story:
        rows = getattr(flowable, "_cellvalues", None)
        if not rows:
            continue
        for row in rows:
            for cell in row:
                nested = getattr(cell, "_cellvalues", None)
                if nested and len(nested) == 1 and len(nested[0]) == 1:
                    return cell
                found = _find_badge([cell]) if nested else None
                if found is not None:
                    return found
    return None


def _badge_fill(badge) -> object:
    """Return the background colour a badge table is styled with."""
    for command in badge._bkgrndcmds:
        if command[0] == "BACKGROUND":
            return command[3]
    raise AssertionError("the badge carries no BACKGROUND command")


class TestAgreementBadge:
    """The verdict is shown in colour and in words, as the card on the page is."""

    @pytest.mark.parametrize(
        ("agreement", "field"),
        [
            (AgreementLevel.HIGH, "agreement_high"),
            (AgreementLevel.MODERATE, "agreement_moderate"),
            (AgreementLevel.LOW, "agreement_low"),
        ],
    )
    def test_the_badge_is_filled_with_the_colour_of_its_level(
        self, agreement: AgreementLevel, field: str
    ):
        """Each level fills the badge itself with that level's token."""
        # GIVEN a result read at one agreement level
        palette = get_palette(ReportTheme.LIGHT)
        renderer = PdfResultRenderer(palette)

        # WHEN the story is assembled
        badge = _find_badge(renderer._story(_data(agreement), get_labels(ReportLang.EN)))

        # THEN the badge exists and carries that colour
        assert badge is not None, "the compromise card has no badge"
        assert _badge_fill(badge) is getattr(palette, field)

    @pytest.mark.parametrize("lang", list(ReportLang))
    def test_the_badge_uses_the_wording_of_the_card_on_the_page(self, lang: ReportLang):
        """The card's badge reads "High Confidence", not "High agreement".

        The page labels its two badges differently by position, and this one sits
        where the card's badge sits.
        """
        # GIVEN the labels for one language
        labels = get_labels(lang)
        renderer = PdfResultRenderer(get_palette(ReportTheme.LIGHT))

        # WHEN the badge is found
        badge = _find_badge(renderer._story(_data(AgreementLevel.HIGH), labels))

        # THEN it spells the level and the word the card uses
        assert badge is not None
        text = badge._cellvalues[0][0].text
        assert labels.confidence_levels["high"] in text
        assert labels.confidence in text


class TestNothingOverflowsThePage:
    """Every table fits what its parent actually leaves it, not just the page."""

    def test_no_table_is_wider_than_the_space_it_sits_in(self):
        """Measured against the parent's inner width, at every nesting depth.

        An earlier version of this test compared every table to the printable page
        width, and so did not notice the triple inside the compromise card: it was
        two points too wide for the card's padding while still narrower than the
        page. Verified by putting the hardcoded widths back -- that version passed,
        this one fails.
        """
        # GIVEN a rendered story
        renderer = PdfResultRenderer(get_palette(ReportTheme.LIGHT))
        story = renderer._story(_data(), get_labels(ReportLang.EN))

        def check(flowables, available: float, where: str) -> None:
            """Assert each table fits ``available``, then recurse into its cells."""
            for flowable in flowables:
                cols = getattr(flowable, "_colWidths", None)
                rows = getattr(flowable, "_cellvalues", None)
                if not cols or not all(isinstance(c, int | float) for c in cols):
                    continue
                total = sum(cols)
                assert total <= available + 0.01, (
                    f"{where}: table of {total:.2f}pt in {available:.2f}pt of space"
                )
                if not rows:
                    continue
                # A nested table gets its column's width, less this table's padding.
                padding = 2 * _CARD_PADDING if total == pytest.approx(_CONTENT_WIDTH) else 0
                for row in rows:
                    for column, cell in enumerate(row):
                        inner = cols[column] - padding
                        check([cell], inner, f"{where} > column {column}")

        # WHEN each table is measured against the space its parent leaves
        # THEN none of them overflows it
        check(story, _CONTENT_WIDTH, "story")


class TestConfidenceBar:
    """The Δmax bar shows the share of the scale, filled and stated."""

    @pytest.mark.parametrize(
        ("max_error", "expected_share"),
        [(0.0, 0.0), (20.0, 0.2), (50.0, 0.5), (100.0, 1.0), (140.0, 1.0)],
    )
    def test_the_filled_width_is_the_share_of_the_scale(
        self, max_error: float, expected_share: float
    ):
        """The fill is Δmax over the scale's width, clamped at full.

        An error wider than the scale is possible arithmetic, and the page clamps
        it the same way rather than drawing past the end of the bar.
        """
        # GIVEN a result whose error is some share of a 0-100 scale
        data = replace(_data(), max_error=max_error)
        renderer = PdfResultRenderer(get_palette(ReportTheme.LIGHT))

        # WHEN the bar is built
        row = renderer._confidence_bar(data, get_labels(ReportLang.EN))
        drawing = row._cellvalues[0][1]
        track, *fill = drawing.contents

        # THEN the filled rectangle covers exactly that share of the track
        drawn = fill[0].width if fill else 0.0
        assert drawn == pytest.approx(track.width * expected_share)

    def test_a_zero_error_draws_no_fill_at_all(self):
        """Nothing is drawn rather than a zero-width rectangle."""
        # GIVEN a result with no error
        data = replace(_data(), max_error=0.0)

        # WHEN the bar is built
        row = PdfResultRenderer(get_palette(ReportTheme.LIGHT))._confidence_bar(
            data, get_labels(ReportLang.EN)
        )

        # THEN only the track is present
        assert len(row._cellvalues[0][1].contents) == 1

    def test_the_caption_states_the_share_as_a_percentage(self):
        """The reader gets the share in words as well as in bar length."""
        # GIVEN an error of a fifth of the scale
        data = replace(_data(), max_error=20.0)

        # WHEN the bar is built
        row = PdfResultRenderer(get_palette(ReportTheme.LIGHT))._confidence_bar(
            data, get_labels(ReportLang.EN)
        )

        # THEN the caption names that share
        assert "20%" in row._cellvalues[0][0].text
