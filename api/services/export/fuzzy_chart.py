"""Draw the BeCoMe fuzzy-triangle visualization as a reportlab Drawing.

Each aggregated fuzzy number is a triangle with vertices ``(lower, 0)``,
``(peak, 1)`` and ``(upper, 0)``; the three are overlaid on shared axes so the
PDF mirrors the "Triangle" chart from the web UI. Colours come from the report
palette, so they follow the theme exactly as the web legend does: blue mean, green
median, and a best compromise drawn in the foreground ink -- near-black on a light
page, near-white on a dark one, which is what ``currentColor`` gives it on the web.
"""

from collections.abc import Callable

from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, String
from reportlab.pdfbase.pdfmetrics import stringWidth

from api.services.export.data import ResultExportData
from api.services.export.fonts import FONT_MONO, FONT_SANS, register_fonts
from api.services.export.labels import ResultLabels
from api.services.export.theme import ExportPalette

_WIDTH = 440.0
_HEIGHT = 230.0
_PLOT_X0 = 42.0
_PLOT_X1 = _WIDTH - 16.0
_PLOT_Y0 = 38.0
_PLOT_Y1 = _HEIGHT - 30.0

_TICK_SIZE = 8
_LEGEND_SIZE = 9


def build_triangle_chart(
    data: ResultExportData, labels: ResultLabels, palette: ExportPalette
) -> Drawing:
    """Build the overlaid fuzzy-triangle chart for a result export.

    :param data: Assembled result data (provides the scale and the three
        aggregated fuzzy numbers).
    :param labels: Localized labels for the legend and axis caption.
    :param palette: Colours for this report's theme.
    :return: A reportlab Drawing flowable ready to add to a PDF story.
    """
    register_fonts()
    drawing = Drawing(_WIDTH, _HEIGHT)
    span = data.scale_max - data.scale_min

    def to_x(value: float) -> float:
        return _PLOT_X0 + (value - data.scale_min) / span * (_PLOT_X1 - _PLOT_X0)

    def to_y(membership: float) -> float:
        return _PLOT_Y0 + membership * (_PLOT_Y1 - _PLOT_Y0)

    _add_axes(drawing, data, to_x, to_y, palette)
    triangles = (
        (data.arithmetic_mean, palette.chart_mean),
        (data.median, palette.chart_median),
        (data.best_compromise, palette.foreground),
    )
    for triple, color in triangles:
        drawing.add(
            PolyLine(
                points=[
                    to_x(triple.lower),
                    to_y(0.0),
                    to_x(triple.peak),
                    to_y(1.0),
                    to_x(triple.upper),
                    to_y(0.0),
                ],
                strokeColor=color,
                strokeWidth=2,
            )
        )
    _add_legend(drawing, labels, palette)
    return drawing


def _add_axes(
    drawing: Drawing,
    data: ResultExportData,
    to_x: Callable[[float], float],
    to_y: Callable[[float], float],
    palette: ExportPalette,
) -> None:
    """Draw the plot box, membership ticks and value ticks."""
    drawing.add(Line(_PLOT_X0, _PLOT_Y0, _PLOT_X1, _PLOT_Y0, strokeColor=palette.grid))
    drawing.add(Line(_PLOT_X0, _PLOT_Y0, _PLOT_X0, _PLOT_Y1, strokeColor=palette.grid))
    for membership in (0.0, 1.0):
        drawing.add(
            String(
                _PLOT_X0 - 6,
                to_y(membership) - 3,
                f"{membership:.0f}",
                fontName=FONT_MONO,
                fontSize=_TICK_SIZE,
                fillColor=palette.subtitle,
                textAnchor="end",
            )
        )
    mid = (data.scale_min + data.scale_max) / 2
    ticks = ((data.scale_min, "start"), (mid, "middle"), (data.scale_max, "end"))
    for value, anchor in ticks:
        drawing.add(
            String(
                to_x(value),
                _PLOT_Y0 - 12,
                f"{value:.1f}",
                fontName=FONT_MONO,
                fontSize=_TICK_SIZE,
                fillColor=palette.subtitle,
                textAnchor=anchor,
            )
        )


def _add_legend(
    drawing: Drawing, labels: ResultLabels, palette: ExportPalette, left: float = _PLOT_X0
) -> None:
    """Draw a horizontal legend strip along the top of the drawing.

    The height comes from the drawing rather than from a module constant: the
    landscape and centroid strips are half the height of the triangle plot, and a
    fixed offset put their legends outside their own canvas, where they overprinted
    the table below. Caught by looking at a rendered page, not by a test.

    :param drawing: Drawing to add the legend to.
    :param labels: Localized labels for the three series.
    :param palette: Colours for this report's theme.
    :param left: Left edge to start the strip at.
    """
    entries = (
        (palette.chart_mean, labels.legend_mean),
        (palette.chart_median, labels.legend_median),
        (palette.foreground, labels.legend_best),
    )
    x = left
    legend_y = drawing.height - 10
    for color, text in entries:
        drawing.add(Line(x, legend_y, x + 16, legend_y, strokeColor=color, strokeWidth=2))
        drawing.add(
            String(
                x + 20,
                legend_y - 3,
                text,
                fontName=FONT_SANS,
                fontSize=_LEGEND_SIZE,
                fillColor=palette.subtitle,
            )
        )
        x += 20 + stringWidth(text, FONT_SANS, _LEGEND_SIZE) + 18


# Landscape and Centroid keep the page's own proportions: it draws them in a
# 400x100 viewBox with the axis inset 40 on the left and 320 wide, so the same
# tenth-of-width inset is used here rather than a second set of numbers.
_STRIP_WIDTH = 440.0
_STRIP_HEIGHT = 118.0
_STRIP_INSET = _STRIP_WIDTH * 0.1
_STRIP_SPAN = _STRIP_WIDTH * 0.8


def _strip_axis(
    drawing: Drawing,
    data: ResultExportData,
    palette: ExportPalette,
    axis_y: float,
    bounds: tuple[float, float] | None = None,
) -> Callable[[float], float]:
    """Draw a horizontal scale axis with its end labels, and return its mapping.

    :param drawing: Drawing to add the axis to.
    :param data: Assembled result data, for the scale bounds.
    :param palette: Colours for this report's theme.
    :param axis_y: Height at which to draw the axis.
    :param bounds: Range the axis covers, defaulting to the project's full scale.
    :return: Function mapping a value on that range to an x coordinate.
    """
    low, high = bounds if bounds else (data.scale_min, data.scale_max)
    span = high - low

    def to_x(value: float) -> float:
        share = (value - low) / span if span else 0.0
        return _STRIP_INSET + share * _STRIP_SPAN

    drawing.add(
        Line(
            _STRIP_INSET,
            axis_y,
            _STRIP_INSET + _STRIP_SPAN,
            axis_y,
            strokeColor=palette.grid,
        )
    )
    for value, anchor in ((low, "start"), (high, "end")):
        drawing.add(
            String(
                to_x(value),
                axis_y - 14,
                f"{value:.1f}",
                fontName=FONT_MONO,
                fontSize=_TICK_SIZE,
                fillColor=palette.subtitle,
                textAnchor=anchor,
            )
        )
    return to_x


def _anchored(x: float, text: str, size: float, width: float) -> tuple[float, str]:
    """Place a centred label so it cannot run off either edge of the drawing.

    A ``Drawing`` does not clip: a label centred on a value near the start of the
    scale is drawn straight past the left edge and into the page margin. Near an
    edge the label is anchored to that edge instead of to its own middle.

    :param x: Preferred centre for the label.
    :param text: The label itself, for its measured width.
    :param size: Font size the label is drawn at.
    :param width: Width of the drawing the label must stay inside.
    :return: The x to draw at, and the anchor to draw it with.
    """
    half = stringWidth(text, FONT_SANS, size) / 2
    if x - half < 0:
        return 0.0, "start"
    if x + half > width:
        return width, "end"
    return x, "middle"


def build_landscape_chart(
    data: ResultExportData, labels: ResultLabels, palette: ExportPalette
) -> Drawing:
    """Build the landscape view: every opinion on one axis, aggregates marked.

    This is the view the page opens on, which is why the report leads with it. It
    answers a question the triangles cannot at a glance: whether the panel is one
    cluster or two, and where the compromise sits relative to them.

    :param data: Assembled result data.
    :param labels: Localized labels for the legend.
    :param palette: Colours for this report's theme.
    :return: A reportlab Drawing flowable ready to add to a PDF story.
    """
    register_fonts()
    drawing = Drawing(_STRIP_WIDTH, _STRIP_HEIGHT)
    axis_y = 46.0
    to_x = _strip_axis(drawing, data, palette, axis_y)

    for opinion in data.opinions:
        drawing.add(
            Circle(
                to_x(opinion.centroid),
                axis_y,
                4,
                fillColor=palette.subtitle,
                fillOpacity=0.5,
                strokeColor=None,
            )
        )

    for triple, colour in (
        (data.arithmetic_mean, palette.chart_mean),
        (data.median, palette.chart_median),
    ):
        x = to_x(triple.centroid)
        drawing.add(Line(x, axis_y - 10, x, axis_y + 10, strokeColor=colour, strokeWidth=2))

    best_x = to_x(data.best_compromise.centroid)
    drawing.add(
        Line(
            best_x,
            axis_y - 18,
            best_x,
            axis_y + 22,
            strokeColor=palette.foreground,
            strokeWidth=2.5,
        )
    )
    drawing.add(Circle(best_x, axis_y, 5, fillColor=palette.primary, strokeColor=None))
    caption = f"{labels.best_short} {data.best_compromise.centroid:.2f} \u00b1 {data.max_error:.2f}"
    caption_x, anchor = _anchored(best_x, caption, 9, drawing.width)
    drawing.add(
        String(
            caption_x,
            axis_y + 28,
            caption,
            fontName=FONT_SANS,
            fontSize=9,
            fillColor=palette.foreground,
            textAnchor=anchor,
        )
    )
    _add_legend(drawing, labels, palette, left=_STRIP_INSET)
    return drawing


def _centroid_bounds(data: ResultExportData) -> tuple[float, float]:
    """Return the range the centroid view covers: the data, plus breathing room.

    The page zooms this view to the opinions rather than showing the whole scale,
    and that is the point of it: collapsed to single points on a full scale, a
    tight panel becomes one indistinguishable blob, which is the opposite of what
    the view is for. Padding is 15% of the spread, or 5 units when every centroid
    coincides -- the same rule the page uses.

    :param data: Assembled result data.
    :return: Lower and upper bound of the axis.
    """
    values = [opinion.centroid for opinion in data.opinions] or [
        data.scale_min,
        data.scale_max,
    ]
    values += [
        data.arithmetic_mean.centroid,
        data.median.centroid,
        data.best_compromise.centroid,
    ]
    low, high = min(values), max(values)
    padding = (high - low) * 0.15 or 5.0
    return low - padding, high + padding


def build_centroid_chart(
    data: ResultExportData, labels: ResultLabels, palette: ExportPalette
) -> Drawing:
    """Build the centroid view: one dot per opinion, aggregates as dashed lines.

    Collapsing each opinion to its centre of gravity turns a crowd of overlapping
    triangles into something countable, which is what settles the question of
    whether a small Δmax means the panel agreed.

    :param data: Assembled result data.
    :param labels: Localized labels for the legend.
    :param palette: Colours for this report's theme.
    :return: A reportlab Drawing flowable ready to add to a PDF story.
    """
    register_fonts()
    drawing = Drawing(_STRIP_WIDTH, _STRIP_HEIGHT)
    axis_y = 46.0
    to_x = _strip_axis(drawing, data, palette, axis_y, bounds=_centroid_bounds(data))

    for opinion in data.opinions:
        drawing.add(
            Circle(
                to_x(opinion.centroid),
                axis_y,
                3.5,
                fillColor=palette.primary,
                fillOpacity=0.7,
                strokeColor=None,
            )
        )

    for triple, colour in (
        (data.arithmetic_mean, palette.chart_mean),
        (data.median, palette.chart_median),
        (data.best_compromise, palette.primary),
    ):
        x = to_x(triple.centroid)
        drawing.add(
            Line(
                x,
                axis_y - 16,
                x,
                axis_y + 20,
                strokeColor=colour,
                strokeWidth=1.5,
                strokeDashArray=[6, 3],
            )
        )
    _add_legend(drawing, labels, palette, left=_STRIP_INSET)
    return drawing
