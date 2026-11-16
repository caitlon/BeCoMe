"""Tests for the report's typefaces and their glyph coverage.

reportlab has no per-glyph fallback: a character the face lacks is drawn as
``.notdef`` with no exception and no log line, and every existing renderer test
would still pass. These tests are what turns that silence into a red build.
"""

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from datetime import UTC, datetime

import pytest
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from api.services.agreement_level import AgreementLevel
from api.services.export import fonts as fonts_module
from api.services.export.data import (
    FuzzyTriple,
    OpinionRow,
    ReportLang,
    ResultExportData,
)
from api.services.export.fonts import (
    FONT_DISPLAY,
    FONT_MONO,
    FONT_SANS,
    FONT_SANS_BOLD,
    font_for,
    register_fonts,
)
from api.services.export.labels import ResultLabels, get_labels
from api.services.export.renderers import PdfResultRenderer
from api.services.export.theme import ReportTheme, get_palette


def _export_data() -> ResultExportData:
    """Build a result whose text exercises Czech diacritics and the method's Greek."""
    return ResultExportData(
        project_name="Protipovodňová opatření",
        project_description=None,
        scale_min=0.0,
        scale_max=100.0,
        scale_unit="%",
        generated_at=datetime(2026, 9, 8, tzinfo=UTC),
        num_experts=1,
        max_error=5.97,
        agreement=AgreementLevel.HIGH,
        best_compromise=FuzzyTriple(11.54, 14.19, 17.19),
        arithmetic_mean=FuzzyTriple(10.0, 13.0, 16.0),
        median=FuzzyTriple(12.0, 15.0, 18.0),
        likert_value=None,
        likert_decision=None,
        opinions=(OpinionRow("Jan Novák", "Vedoucí oddělení", 10.0, 14.0, 18.0),),
    )


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


class TestHeadingsUseTheDisplayFace:
    """Headings are set in Playfair, as `CardTitle` is on the page."""

    @pytest.mark.parametrize("lang", list(ReportLang))
    def test_renderer_sets_section_headings_in_the_display_face(self, lang: ReportLang):
        """The rendered story's headings carry Playfair, in both languages.

        This asks the renderer, not the helper it uses. An earlier version of this
        test called ``font_for`` with the same expression the renderer uses, which
        proved only that the helper agrees with itself: putting ``FONT_SANS_BOLD``
        back into the heading style left it green.

        Reading the embedded fonts out of the finished PDF would not close the gap
        either, because Playfair arrives there anyway through the report title.
        """
        # GIVEN a report about to be built in one language
        renderer = PdfResultRenderer(get_palette(ReportTheme.LIGHT))

        # WHEN its flowables are assembled
        story = renderer._story(_export_data(), get_labels(lang))

        # THEN every section heading is set in the display face
        headings = [
            flowable
            for flowable in story
            if getattr(getattr(flowable, "style", None), "name", None) == "heading"
        ]
        assert len(headings) == 3, "expected the results, chart and opinions headings"
        assert {heading.style.fontName for heading in headings} == {FONT_DISPLAY}


def _paragraph_texts(flowables) -> list[str]:
    """Collect the markup of every paragraph, including those inside tables.

    The compromise card and the Δmax row are tables, so the figures worth checking
    no longer sit at the top level of the story.

    :param flowables: Story, or the cells of one table.
    :return: Every paragraph's source markup, in document order.
    """
    texts: list[str] = []
    for flowable in flowables:
        text = getattr(flowable, "text", None)
        if isinstance(text, str):
            texts.append(text)
        rows = getattr(flowable, "_cellvalues", None)
        if rows:
            for row in rows:
                texts.extend(_paragraph_texts(row))
    return texts


class TestNumbersUseTheMonoFace:
    """Figures are monospaced in the report, as they are on the page."""

    def test_summary_numbers_are_set_in_the_mono_face(self):
        """Δmax and the expert count carry the mono face, not body text.

        Both are wrapped in `font-mono` on the results page. They sit inside running
        text rather than the numeric columns of a table, so the table style that
        monospaces those columns does not reach them.
        """
        # GIVEN a rendered story
        renderer = PdfResultRenderer(get_palette(ReportTheme.LIGHT))
        labels = get_labels(ReportLang.EN)

        # WHEN the paragraphs carrying those two figures are found
        texts = [
            text
            for text in _paragraph_texts(renderer._story(_export_data(), labels))
            if labels.max_error in text or labels.experts in text
        ]

        # THEN each sets its number in the mono face
        assert len(texts) == 2, f"expected the max-error and expert-count lines, got {texts}"
        for text in texts:
            assert f'<font name="{FONT_MONO}">' in text, text


class TestFallbackKeepsWeight:
    """The fallback face is the caller's choice, so a bold context stays bold."""

    def test_a_bold_caller_falls_back_to_the_bold_face(self):
        """A string the display face cannot draw keeps its weight on the way out.

        Falling back to the regular face would change typeface and weight at once,
        which reads as a rendering fault rather than a substitution. Nothing in the
        report reaches this branch today -- both locales' headings are covered by
        Playfair -- so without this test the parameter would be unverified.
        """
        # GIVEN a heading that carries the one glyph Playfair lacks
        heading = "Výsledky (Γ)"

        # WHEN a bold caller asks for a face
        chosen = font_for(heading, FONT_DISPLAY, fallback=FONT_SANS_BOLD)

        # THEN it gets the bold fallback, not the regular one
        assert chosen == FONT_SANS_BOLD


@pytest.fixture
def fresh_font_registry(monkeypatch: pytest.MonkeyPatch):
    """Give reportlab a registry without the report's faces, as a new process has.

    The faces are module-global in reportlab, so once any earlier test has
    registered them the race below can never happen again in this process. The
    registry is swapped rather than cleared, and the original comes back after the
    test, so the tests that run later still find the faces in place.
    """
    ours = {FONT_SANS, FONT_SANS_BOLD, FONT_MONO, FONT_DISPLAY}
    fresh = {name: font for name, font in pdfmetrics._fonts.items() if name not in ours}
    monkeypatch.setattr(pdfmetrics, "_fonts", fresh)


class TestConcurrentRegistration:
    """The first exports after a cold start must not see a half-filled registry."""

    def test_concurrent_first_exports_all_render(
        self, fresh_font_registry, monkeypatch: pytest.MonkeyPatch
    ):
        """Every one of several simultaneous first PDF exports renders.

        Registration reads four TrueType files one after another. A request that
        arrived while another was still in that loop used to find the first face
        registered, take that as "all done", and fail on a later face with
        ``KeyError: 'PlayfairDisplay'``. Here one export starts first and the rest
        arrive exactly inside that window: once the first face is registered and
        the next file is still loading.
        """
        # GIVEN a first export whose later font files take a while to load
        real_ttfont = fonts_module.TTFont
        first_face_registered = threading.Event()

        def slow_ttfont(name: str, filename: str) -> TTFont:
            if name != FONT_SANS:
                first_face_registered.set()
                time.sleep(0.1)
            return real_ttfont(name, filename)

        monkeypatch.setattr(fonts_module, "TTFont", slow_ttfont)
        labels = get_labels(ReportLang.EN)

        def export(*, wait_for_first: bool) -> bytes:
            if wait_for_first:
                assert first_face_registered.wait(timeout=5)
            register_fonts()
            return PdfResultRenderer(get_palette(ReportTheme.LIGHT)).render(_export_data(), labels)

        # WHEN the other exports arrive while the first is still registering
        latecomers = 7
        with ThreadPoolExecutor(max_workers=latecomers + 1) as pool:
            futures = [pool.submit(export, wait_for_first=False)]
            futures += [pool.submit(export, wait_for_first=True) for _ in range(latecomers)]
            errors = [future.exception() for future in futures]

        # THEN none of them fails and every face ends up registered
        assert errors == [None] * (latecomers + 1)
        assert {FONT_SANS, FONT_SANS_BOLD, FONT_MONO, FONT_DISPLAY} <= set(pdfmetrics._fonts)


class TestConcurrentRendering:
    """Reportlab's per-document font state is shared, so renders must not overlap."""

    def test_concurrent_renders_all_produce_a_pdf(self):
        """Many simultaneous renders with the fonts already registered all succeed.

        The faces are process-global ``TTFont`` objects, and reportlab keeps the
        per-document subset state on them and builds the subset at save time. Two
        builds running at once corrupted each other and failed inside
        ``makeSubset`` with ``KeyError`` or ``IndexError``. A tiny switch interval
        makes the threads interleave inside one render, as a busy server would.
        """
        # GIVEN registered fonts and a thread switch interval short enough to interleave builds
        register_fonts()
        labels = get_labels(ReportLang.EN)
        data = _export_data()
        previous_interval = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)

        def export(_: int) -> bytes:
            return PdfResultRenderer(get_palette(ReportTheme.LIGHT)).render(data, labels)

        # WHEN many renders run at once
        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = [pool.submit(export, index) for index in range(200)]
                errors = [future.exception() for future in futures]
        finally:
            sys.setswitchinterval(previous_interval)

        # THEN every one of them succeeds and returns a PDF
        failed = [error for error in errors if error is not None]
        assert not failed, f"{len(failed)} of {len(errors)} renders failed, first: {failed[0]!r}"
        assert all(future.result().startswith(b"%PDF") for future in futures)
