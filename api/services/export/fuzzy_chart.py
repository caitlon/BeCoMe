"""Draw the BeCoMe fuzzy-triangle visualization as a reportlab Drawing.

Each aggregated fuzzy number is a triangle with vertices ``(lower, 0)``,
``(peak, 1)`` and ``(upper, 0)``; the three are overlaid on shared axes so the
PDF mirrors the "Triangle" chart from the web UI. Colors match the UI legend
(blue mean, green median, dark best compromise).
"""

from collections.abc import Callable

from reportlab.graphics.shapes import Drawing, Line, PolyLine, String
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth

from api.services.export.data import ResultExportData
from api.services.export.fonts import FONT_NAME
from api.services.export.labels import ResultLabels

_WIDTH = 440.0
_HEIGHT = 230.0
_PLOT_X0 = 42.0
_PLOT_X1 = _WIDTH - 16.0
_PLOT_Y0 = 38.0
_PLOT_Y1 = _HEIGHT - 30.0

_AXIS_COLOR = colors.HexColor("#94a3b8")
_MEAN_COLOR = colors.HexColor("#3b82f6")
_MEDIAN_COLOR = colors.HexColor("#22c55e")
_BEST_COLOR = colors.HexColor("#111827")
_TICK_SIZE = 8
_LEGEND_SIZE = 9


def build_triangle_chart(data: ResultExportData, labels: ResultLabels) -> Drawing:
    """Build the overlaid fuzzy-triangle chart for a result export.

    :param data: Assembled result data (provides the scale and the three
        aggregated fuzzy numbers).
    :param labels: Localized labels for the legend and axis caption.
    :return: A reportlab Drawing flowable ready to add to a PDF story.
    """
    drawing = Drawing(_WIDTH, _HEIGHT)
    span = data.scale_max - data.scale_min

    def to_x(value: float) -> float:
        return _PLOT_X0 + (value - data.scale_min) / span * (_PLOT_X1 - _PLOT_X0)

    def to_y(membership: float) -> float:
        return _PLOT_Y0 + membership * (_PLOT_Y1 - _PLOT_Y0)

    _add_axes(drawing, data, to_x, to_y)
    triangles = (
        (data.arithmetic_mean, _MEAN_COLOR),
        (data.median, _MEDIAN_COLOR),
        (data.best_compromise, _BEST_COLOR),
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
    _add_legend(drawing, labels)
    return drawing


def _add_axes(
    drawing: Drawing,
    data: ResultExportData,
    to_x: Callable[[float], float],
    to_y: Callable[[float], float],
) -> None:
    """Draw the plot box, membership ticks and value ticks."""
    drawing.add(Line(_PLOT_X0, _PLOT_Y0, _PLOT_X1, _PLOT_Y0, strokeColor=_AXIS_COLOR))
    drawing.add(Line(_PLOT_X0, _PLOT_Y0, _PLOT_X0, _PLOT_Y1, strokeColor=_AXIS_COLOR))
    for membership in (0.0, 1.0):
        drawing.add(
            String(
                _PLOT_X0 - 6,
                to_y(membership) - 3,
                f"{membership:.0f}",
                fontName=FONT_NAME,
                fontSize=_TICK_SIZE,
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
                fontName=FONT_NAME,
                fontSize=_TICK_SIZE,
                textAnchor=anchor,
            )
        )


def _add_legend(drawing: Drawing, labels: ResultLabels) -> None:
    """Draw a horizontal legend strip above the plot."""
    entries = (
        (_MEAN_COLOR, labels.legend_mean),
        (_MEDIAN_COLOR, labels.legend_median),
        (_BEST_COLOR, labels.legend_best),
    )
    x = _PLOT_X0
    legend_y = _HEIGHT - 14
    for color, text in entries:
        drawing.add(Line(x, legend_y, x + 16, legend_y, strokeColor=color, strokeWidth=2))
        drawing.add(String(x + 20, legend_y - 3, text, fontName=FONT_NAME, fontSize=_LEGEND_SIZE))
        x += 20 + stringWidth(text, FONT_NAME, _LEGEND_SIZE) + 18
