"""Tests for the three chart views the report draws.

The page offers Landscape, Triangle and Centroid, and opens on Landscape. The
report used to carry Triangle alone -- the second tab -- so it showed a view the
reader had probably not been looking at.
"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, String
from reportlab.pdfbase.pdfmetrics import stringWidth

from api.services.agreement_level import AgreementLevel
from api.services.export.data import (
    FuzzyTriple,
    OpinionRow,
    ReportLang,
    ResultExportData,
)
from api.services.export.fuzzy_chart import (
    build_centroid_chart,
    build_landscape_chart,
    build_triangle_chart,
)
from api.services.export.labels import get_labels
from api.services.export.renderers import PdfResultRenderer
from api.services.export.theme import ReportTheme, get_palette


def _data(opinion_count: int = 5) -> ResultExportData:
    """Build a result with a given number of expert opinions."""
    opinions = tuple(
        OpinionRow(f"Expert {i}", "Analyst", 10.0 + i, 14.0 + i, 18.0 + i)
        for i in range(opinion_count)
    )
    return ResultExportData(
        project_name="Flood prevention",
        project_description=None,
        scale_min=0.0,
        scale_max=100.0,
        scale_unit="%",
        generated_at=datetime(2026, 9, 9, tzinfo=UTC),
        num_experts=opinion_count,
        max_error=5.97,
        agreement=AgreementLevel.HIGH,
        best_compromise=FuzzyTriple(11.54, 14.19, 17.19),
        arithmetic_mean=FuzzyTriple(10.0, 13.0, 16.0),
        median=FuzzyTriple(12.0, 15.0, 18.0),
        likert_value=None,
        likert_decision=None,
        opinions=opinions,
    )


def _shapes(drawing: Drawing, kind: type) -> list:
    """Return every shape of one kind in a drawing."""
    return [shape for shape in drawing.contents if isinstance(shape, kind)]


class TestLandscapeChart:
    """One axis, a dot per expert, and the three aggregates marked on it."""

    @pytest.mark.parametrize("count", [1, 5, 13])
    def test_it_draws_one_dot_per_expert(self, count: int):
        """Every opinion gets a dot, however many there are."""
        # GIVEN a panel of a given size
        palette = get_palette(ReportTheme.LIGHT)

        # WHEN the landscape is built
        drawing = build_landscape_chart(_data(count), get_labels(ReportLang.EN), palette)

        # THEN there is a dot for each opinion, plus the compromise marker
        assert len(_shapes(drawing, Circle)) == count + 1

    def test_the_compromise_marker_sits_at_its_centroid(self):
        """The marker's x is the compromise centroid mapped onto the axis."""
        # GIVEN a result
        data = _data()
        palette = get_palette(ReportTheme.LIGHT)

        # WHEN the landscape is built
        drawing = build_landscape_chart(data, get_labels(ReportLang.EN), palette)

        # THEN the largest circle -- the compromise -- is where the value maps
        marker = max(_shapes(drawing, Circle), key=lambda c: c.r)
        share = (data.best_compromise.centroid - data.scale_min) / (data.scale_max - data.scale_min)
        assert marker.cx == pytest.approx(drawing.width * 0.1 + share * drawing.width * 0.8, abs=1)


class TestCentroidChart:
    """One dot per opinion centroid, with the three aggregates as dashed lines."""

    def test_each_aggregate_gets_a_dashed_line(self):
        """Mean, median and compromise are dashed, as they are on the page."""
        # GIVEN a result
        palette = get_palette(ReportTheme.LIGHT)

        # WHEN the centroid view is built
        drawing = build_centroid_chart(_data(), get_labels(ReportLang.EN), palette)

        # THEN exactly three lines are dashed
        dashed = [line for line in _shapes(drawing, Line) if line.strokeDashArray]
        assert len(dashed) == 3

    def test_it_draws_one_dot_per_opinion(self):
        """Every expert's centroid is a dot."""
        # GIVEN a panel of seven
        # WHEN the centroid view is built
        drawing = build_centroid_chart(
            _data(7), get_labels(ReportLang.EN), palette=get_palette(ReportTheme.LIGHT)
        )

        # THEN each opinion is represented
        assert len(_shapes(drawing, Circle)) == 7


class TestAllThreeViewsAreInTheReport:
    """The report carries what the page carries, in the page's order."""

    def test_the_story_holds_three_charts_landscape_first(self):
        """Landscape leads, because that is the tab the page opens on."""
        # GIVEN a rendered story
        renderer = PdfResultRenderer(get_palette(ReportTheme.LIGHT))

        # WHEN its drawings are collected
        story = renderer._story(_data(), get_labels(ReportLang.EN))
        drawings = [f for f in story if isinstance(f, Drawing)]

        # THEN there are three, and the first has a dot per expert
        assert len(drawings) == 3
        assert len(_shapes(drawings[0], Circle)) == len(_data().opinions) + 1
        assert _shapes(drawings[1], PolyLine), "the second view is the triangle"


class TestNothingIsDrawnOutsideItsCanvas:
    """A shape drawn past the drawing's own height overprints what follows it."""

    @pytest.mark.parametrize(
        "build", [build_landscape_chart, build_triangle_chart, build_centroid_chart]
    )
    def test_every_shape_stays_within_the_drawing(self, build):
        """No shape sits above the drawing's height or below zero.

        The legend used to be placed from a module constant sized for the triangle
        plot, so on the half-height strips it landed outside its own canvas and
        printed over the table beneath. Nothing failed; the page had to be looked at.
        """
        # GIVEN one of the three views
        drawing = build(_data(), get_labels(ReportLang.EN), get_palette(ReportTheme.LIGHT))

        # WHEN the vertical extent of every shape is measured
        tops: list[float] = []
        for shape in drawing.contents:
            if isinstance(shape, Circle):
                tops.append(shape.cy + shape.r)
            elif isinstance(shape, Line):
                tops.extend([shape.y1, shape.y2])
            elif isinstance(shape, String):
                tops.append(shape.y + shape.fontSize)
            elif isinstance(shape, PolyLine):
                tops.extend(shape.points[1::2])

        # THEN all of it fits inside the canvas
        assert max(tops) <= drawing.height, f"{max(tops)} > {drawing.height}"
        assert min(tops) >= 0


class TestNothingIsDrawnPastTheSides:
    """Horizontal extents matter as much as vertical ones, and were not checked."""

    @pytest.mark.parametrize("lang", list(ReportLang))
    @pytest.mark.parametrize("centroid", [0.0, 3.0, 50.0, 97.0, 100.0])
    def test_the_compromise_caption_stays_inside_the_drawing(
        self, lang: ReportLang, centroid: float
    ):
        """A compromise at either end of the scale must not push its label off.

        A reportlab Drawing does not clip, so a label centred on a value near the
        scale's start was drawn past the left edge and into the page's own margin --
        closer to the paper edge than anything else in the report. The vertical
        bounds test could not see it.
        """
        # GIVEN a compromise sitting at some point of the scale
        data = replace(_data(), best_compromise=FuzzyTriple(centroid, centroid, centroid))

        # WHEN the landscape is drawn
        drawing = build_landscape_chart(data, get_labels(lang), get_palette(ReportTheme.LIGHT))

        # THEN every label lies within the canvas, whichever way it is anchored
        for shape in drawing.contents:
            if not isinstance(shape, String):
                continue
            width = stringWidth(shape.text, shape.fontName, shape.fontSize)
            left = {
                "start": shape.x,
                "end": shape.x - width,
                "middle": shape.x - width / 2,
            }[shape.textAnchor]
            assert left >= -0.01, f"{shape.text!r} starts at {left:.1f}"
            assert left + width <= drawing.width + 0.01, (
                f"{shape.text!r} ends at {left + width:.1f}, past {drawing.width}"
            )


class TestCentroidZoomsToTheData:
    """The centroid view scales to the opinions, as the page does."""

    def test_a_tight_panel_is_spread_across_the_axis(self):
        """Centroids one unit apart must not collapse into one blob.

        On a full 0-100 scale they would sit within four points of each other,
        which defeats the one thing this view exists to show. The page zooms; so
        does the report.
        """
        # GIVEN a panel whose opinions differ by a single unit, with the aggregates
        # sitting among them as they always do -- they are derived from the same
        # opinions, so an axis that ignored them would leave their markers outside.
        opinions = tuple(
            OpinionRow(f"E{i}", "Analyst", 40.0 + i, 41.0 + i, 42.0 + i) for i in range(3)
        )
        data = replace(
            _data(),
            opinions=opinions,
            arithmetic_mean=FuzzyTriple(40.0, 41.0, 42.0),
            median=FuzzyTriple(41.0, 42.0, 43.0),
            best_compromise=FuzzyTriple(40.5, 41.5, 42.5),
        )

        # WHEN the centroid view is drawn
        drawing = build_centroid_chart(
            data, get_labels(ReportLang.EN), get_palette(ReportTheme.LIGHT)
        )

        # THEN the dots are spread out, not stacked
        dots = sorted(shape.cx for shape in _shapes(drawing, Circle))
        assert dots[-1] - dots[0] > drawing.width / 4

    def test_an_identical_panel_still_draws_an_axis(self):
        """When every centroid coincides the padding falls back to a fixed span."""
        # GIVEN a panel that agrees exactly
        opinions = tuple(OpinionRow(f"E{i}", "A", 40.0, 41.0, 42.0) for i in range(3))
        data = replace(
            _data(),
            opinions=opinions,
            arithmetic_mean=FuzzyTriple(40.0, 41.0, 42.0),
            median=FuzzyTriple(40.0, 41.0, 42.0),
            best_compromise=FuzzyTriple(40.0, 41.0, 42.0),
        )

        # WHEN the centroid view is drawn
        drawing = build_centroid_chart(
            data, get_labels(ReportLang.EN), get_palette(ReportTheme.LIGHT)
        )

        # THEN nothing divides by zero and the dots land in the middle
        dots = [shape.cx for shape in _shapes(drawing, Circle)]
        assert dots
        assert all(0 < x < drawing.width for x in dots)
