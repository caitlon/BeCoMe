"""Unit tests for the export colour theme.

The report is meant to read as a printed copy of the project page, so its
palette is the page's palette. These tests are what stops the two drifting:
the values here are not decoration, they are the interface's own tokens.
"""

import colorsys
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from api.services.export.data import FuzzyTriple, OpinionRow, ReportLang, ResultExportData
from api.services.export.labels import get_labels
from api.services.export.renderers import PdfResultRenderer
from api.services.export.theme import ReportTheme, get_palette
from tests.shared.pdf_inspection import embedded_fonts

_INDEX_CSS = Path(__file__).resolve().parents[4] / "frontend" / "src" / "index.css"


def _export_data() -> ResultExportData:
    """Build a minimal result whose text exercises Czech and the method's Greek."""
    return ResultExportData(
        project_name="Protipovodňová opatření",
        project_description=None,
        scale_min=0.0,
        scale_max=100.0,
        scale_unit="%",
        generated_at=datetime(2026, 9, 8, tzinfo=UTC),
        num_experts=1,
        max_error=5.97,
        best_compromise=FuzzyTriple(11.54, 14.19, 17.19),
        arithmetic_mean=FuzzyTriple(10.0, 13.0, 16.0),
        median=FuzzyTriple(12.0, 15.0, 18.0),
        likert_value=None,
        likert_decision=None,
        opinions=(OpinionRow("Jan Novák", "Vedoucí oddělení", 10.0, 14.0, 18.0),),
    )


class TestExportTheme:
    """Tests for the light and dark report palettes."""

    def test_light_table_header_is_the_interface_neutral_grey(self):
        """The table header uses --muted from index.css, not Tailwind slate.

        `#f1f5f9` (slate-100) carries a blue cast the design system does not
        have: every neutral in the app sits at 0% saturation.
        """
        # GIVEN a report rendered in the light theme
        # WHEN its palette is resolved
        theme = get_palette(ReportTheme.LIGHT)

        # THEN the header matches --muted: 0 0% 96%
        assert theme.table_header.hexval() == "0xf5f5f5"


# Palette field -> CSS custom property it must equal. This mapping IS the
# contract: adding a colour to the report means adding it here too.
_TOKENS = {
    "background": "--background",
    "foreground": "--foreground",
    "table_header": "--muted",
    "subtitle": "--muted-foreground",
    "grid": "--border",
    "chart_mean": "--chart-mean",
    "chart_median": "--chart-median",
}


def _hsl_to_hex(triple: str) -> str:
    """Convert an ``H S% L%`` token body into a lowercase ``0xrrggbb`` string.

    :param triple: Token body as written in the stylesheet, e.g. ``0 0% 96%``.
    :return: The colour as reportlab spells it in :meth:`Color.hexval`.
    """
    h_raw, s_raw, l_raw = triple.split()
    hue = float(h_raw) / 360
    sat = float(s_raw.rstrip("%")) / 100
    light = float(l_raw.rstrip("%")) / 100
    red, green, blue = colorsys.hls_to_rgb(hue, light, sat)
    return "0x" + "".join(f"{round(channel * 255):02x}" for channel in (red, green, blue))


def _css_block(name: str) -> dict[str, str]:
    """Read one selector's custom properties out of the frontend stylesheet.

    :param name: Selector to read, ``:root`` or ``.dark``.
    :return: Mapping of property name to its raw value.
    :raises AssertionError: If the selector is missing from the stylesheet.
    """
    text = _INDEX_CSS.read_text(encoding="utf-8")
    start = text.index(f"  {name} {{")
    body = text[start : text.index("\n  }", start)]
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", body))


@pytest.mark.skipif(
    not _INDEX_CSS.exists(),
    reason=(
        "frontend/src/index.css is absent: the backend Docker image copies only api/ and src/, "
        "so this guard runs in the repository and in CI, never inside the built image"
    ),
)
class TestPaletteMatchesTheInterface:
    """The report palette is the interface palette, and this proves it."""

    @pytest.mark.parametrize(
        ("theme", "selector"),
        [(ReportTheme.LIGHT, ":root"), (ReportTheme.DARK, ".dark")],
    )
    def test_every_report_colour_equals_its_css_token(self, theme: ReportTheme, selector: str):
        """Each palette field equals the custom property it mirrors.

        Without this the failure is silent: someone retunes a colour in
        index.css, the page moves, the PDF does not, and nothing goes red.
        """
        # GIVEN the tokens the stylesheet declares for this theme
        declared = _css_block(selector)

        # WHEN the report palette for the same theme is resolved
        palette = get_palette(theme)

        # THEN every colour matches, and the message names the drift
        for field, token in _TOKENS.items():
            assert token in declared, f"{token} vanished from index.css {selector}"
            expected = _hsl_to_hex(declared[token])
            actual = getattr(palette, field).hexval()
            assert actual == expected, (
                f"{theme.value} theme: {field} is {actual}, but {token} in index.css is {expected}"
            )


class TestReportTypography:
    """The report is set in the interface's faces, not in a stand-in."""

    def test_report_is_set_in_the_interface_fonts(self):
        """A rendered report embeds Inter, JetBrains Mono and Playfair Display.

        DejaVu was a stand-in chosen for coverage, and it makes the document look
        like it came from somewhere else than the page that produced it.

        Helvetica and Times-Roman also appear in the document's font resources and
        are deliberately not asserted against: reportlab declares them on every
        canvas, and measurement shows they draw nothing at all.
        """
        # GIVEN a result to render
        data = _export_data()

        # WHEN the report is produced
        content = PdfResultRenderer(get_palette(ReportTheme.LIGHT)).render(
            data, get_labels(ReportLang.EN)
        )

        # THEN the faces the interface uses are the faces embedded
        families = {name.split("-")[0] for name in embedded_fonts(content)}
        assert "Inter" in families
        assert "JetBrainsMono" in families
        assert "PlayfairDisplay" in families
        assert "DejaVuSans" not in families
