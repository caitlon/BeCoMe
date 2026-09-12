"""Colour palettes for the result report, mirroring the web interface.

The report is a printed analogue of the project page, so it borrows the page's
tokens rather than inventing its own. Every value here is a custom property from
``frontend/src/index.css`` -- ``:root`` for light, ``.dark`` for dark -- converted
from HSL to hex, and ``test_export_theme.py`` fails if the two ever disagree.

Two things this replaced, both worth remembering. The greys were Tailwind slate
(``#f1f5f9``, ``#cbd5e1``, ``#475569``), tinted about 215 degrees blue, while every
neutral in the design system sits at 0% saturation. And the chart series, whose
comment claimed they matched the interface, were off by one in each channel:
``#3b82f6`` is Tailwind blue-500, whereas ``hsl(217 91% 60%)`` resolves to
``#3c83f6``. Neither was visible; both were drift.

The palette carries only colours something actually draws.
"""

from dataclasses import dataclass
from enum import StrEnum

from reportlab.lib import colors


class ReportTheme(StrEnum):
    """Theme a report is rendered in, mirroring the interface's resolved theme.

    There is no ``system`` member on purpose: the server cannot know the reader's
    operating system, so resolving it here would be a guess. The client sends the
    theme it already resolved.
    """

    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True, slots=True)
class ExportPalette:
    """Colours used to render a report in one theme.

    :ivar background: Page fill, from ``--background``.
    :ivar foreground: Body text and the triangle's compromise line, from ``--foreground``.
    :ivar primary: The compromise marker on the strip charts, from ``--primary``.
    :ivar table_header: Fill behind table header rows, from ``--muted``.
    :ivar subtitle: Secondary text and axis labels, from ``--muted-foreground``.
    :ivar grid: Table rules and chart axes, from ``--border``.
    :ivar chart_mean: Arithmetic-mean series, from ``--chart-mean``.
    :ivar chart_median: Median series, from ``--chart-median``.
    :ivar agreement_high: Badge fill for high agreement, from ``--success``.
    :ivar agreement_moderate: Badge fill for moderate agreement, from ``--warning``.
    :ivar agreement_low: Badge fill for low agreement, from ``--error``.
    """

    background: colors.Color
    foreground: colors.Color
    primary: colors.Color
    table_header: colors.Color
    subtitle: colors.Color
    grid: colors.Color
    chart_mean: colors.Color
    chart_median: colors.Color
    agreement_high: colors.Color
    agreement_moderate: colors.Color
    agreement_low: colors.Color


_LIGHT = ExportPalette(
    background=colors.HexColor("#ffffff"),
    foreground=colors.HexColor("#1a1a1a"),
    primary=colors.HexColor("#000000"),
    table_header=colors.HexColor("#f5f5f5"),
    subtitle=colors.HexColor("#595959"),
    grid=colors.HexColor("#e6e6e6"),
    chart_mean=colors.HexColor("#3c83f6"),
    chart_median=colors.HexColor("#21c45d"),
    agreement_high=colors.HexColor("#357937"),
    agreement_moderate=colors.HexColor("#c75c05"),
    agreement_low=colors.HexColor("#c62a2a"),
)

_DARK = ExportPalette(
    background=colors.HexColor("#0a0a0a"),
    foreground=colors.HexColor("#fafafa"),
    primary=colors.HexColor("#ffffff"),
    table_header=colors.HexColor("#262626"),
    subtitle=colors.HexColor("#a1a1a1"),
    grid=colors.HexColor("#2b2b2b"),
    chart_mean=colors.HexColor("#61a6fa"),
    chart_median=colors.HexColor("#4ade80"),
    agreement_high=colors.HexColor("#357937"),
    agreement_moderate=colors.HexColor("#f9811f"),
    agreement_low=colors.HexColor("#d33131"),
)


def get_palette(theme: ReportTheme) -> ExportPalette:
    """Return the palette for a theme.

    :param theme: Theme the report is rendered in.
    :return: Palette holding that theme's colours.
    """
    return _DARK if theme == ReportTheme.DARK else _LIGHT
