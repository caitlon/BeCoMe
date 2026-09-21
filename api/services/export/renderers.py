"""Renderers that serialize result data into a downloadable CSV or PDF.

The two renderers share a small ``ResultRenderer`` Strategy interface so the
service can pick one by format and stay open for new formats.
"""

import csv
import io
from abc import ABC, abstractmethod

from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from api.services.agreement_level import AgreementLevel
from api.services.export.data import ExportFormat, ResultExportData
from api.services.export.fonts import (
    FONT_DISPLAY,
    FONT_MONO,
    FONT_SANS,
    FONT_SANS_BOLD,
    font_for,
    register_fonts,
)
from api.services.export.fuzzy_chart import (
    build_centroid_chart,
    build_landscape_chart,
    build_triangle_chart,
)
from api.services.export.labels import ResultLabels
from api.services.export.theme import ExportPalette, ReportTheme, get_palette


def _n2(value: float) -> str:
    """Format a number with two decimals for human-facing report cells."""
    return f"{value:.2f}"


def _n4(value: float) -> str:
    """Format a number with four decimals for machine-facing CSV cells."""
    return f"{value:.4f}"


def _decision(data: ResultExportData, labels: ResultLabels) -> str | None:
    """Return the Likert decision localized for the report language.

    :param data: Assembled result data.
    :param labels: Localized report labels (carry the Czech decision texts).
    :return: Decision text, or None when the project has no Likert reading.
    """
    if data.likert_value is None:
        return data.likert_decision
    return labels.likert_decisions.get(data.likert_value, data.likert_decision)


def _thirds(width: float) -> list[float]:
    """Split a width into three columns that add up to exactly it.

    :param width: Total width to divide.
    :return: Three column widths whose sum is ``width``.
    """
    third = width / 3
    return [third, third, width - 2 * third]


def _mono_centered(ink: colors.Color) -> ParagraphStyle:
    """Build the centred monospace style the compromise card sets its triple in.

    :param ink: Text colour for the current theme.
    :return: A paragraph style for one figure of the triple.
    """
    return ParagraphStyle(
        "card_triple",
        fontName=FONT_MONO,
        fontSize=11,
        leading=14,
        alignment=TA_CENTER,
        textColor=ink,
    )


def _mono(text: str) -> str:
    """Wrap a number in the monospace face, the way the page sets its figures.

    Every numeric value on the results page carries ``font-mono``; inside a
    paragraph of running text the only way to say that is inline markup.

    :param text: Already-formatted number.
    :return: Paragraph markup setting it in :data:`FONT_MONO`.
    """
    return f'<font name="{FONT_MONO}">{text}</font>'


def _escape(text: str) -> str:
    """Escape the XML special characters reportlab Paragraph markup parses."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_CSV_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")

# Page geometry, derived rather than guessed. The first version hardcoded 523 for
# the card and 167 for each third of its triple, which overflowed the card's own
# padding by two points -- invisible on screen, and still outside the frame.
_MARGIN = 36
_CONTENT_WIDTH = A4[0] - 2 * _MARGIN
_CARD_PADDING = 12


def _csv_safe(value: str) -> str:
    """Neutralize spreadsheet formula injection in a CSV cell value.

    Excel and Google Sheets evaluate a cell whose text starts with ``=``, ``+``,
    ``-`` or ``@`` (or a leading tab/CR) as a formula, so a crafted expert name or
    position could run when an admin opens the export. Prefixing such values with
    a single quote forces the spreadsheet to read them as plain text.

    :param value: Raw cell text.
    :return: The value, quote-prefixed when it could be read as a formula.
    """
    if value and value[0] in _CSV_FORMULA_TRIGGERS:
        return "'" + value
    return value


class ResultRenderer(ABC):
    """Strategy that serializes result data into downloadable file bytes."""

    media_type: str
    extension: str

    @abstractmethod
    def render(self, data: ResultExportData, labels: ResultLabels) -> bytes:
        """Serialize the result data into file bytes.

        :param data: Assembled result data.
        :param labels: Localized report labels.
        :return: Encoded file content.
        """


class CsvResultRenderer(ResultRenderer):
    """Serialize result data as UTF-8 CSV: opinions table then a summary."""

    media_type = "text/csv"
    extension = "csv"

    def render(self, data: ResultExportData, labels: ResultLabels) -> bytes:
        """Render the result as a UTF-8 (BOM) CSV document.

        :param data: Assembled result data.
        :param labels: Localized report labels.
        :return: CSV bytes encoded as utf-8-sig so spreadsheets detect UTF-8.
        """
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        def write_row(cells: list[str]) -> None:
            writer.writerow([_csv_safe(cell) for cell in cells])

        write_row([labels.opinions_heading])
        write_row(
            [
                labels.col_expert,
                labels.col_position,
                labels.col_lower,
                labels.col_peak,
                labels.col_upper,
                labels.col_centroid,
            ]
        )
        for opinion in data.opinions:
            write_row(
                [
                    opinion.expert_name,
                    opinion.position,
                    _n4(opinion.lower),
                    _n4(opinion.peak),
                    _n4(opinion.upper),
                    _n4(opinion.centroid),
                ]
            )

        write_row([])
        write_row([labels.results_heading])
        write_row(["", labels.col_lower, labels.col_peak, labels.col_upper, labels.col_centroid])
        for label, triple in (
            (labels.best_compromise, data.best_compromise),
            (labels.arithmetic_mean, data.arithmetic_mean),
            (labels.median, data.median),
        ):
            write_row(
                [
                    label,
                    _n4(triple.lower),
                    _n4(triple.peak),
                    _n4(triple.upper),
                    _n4(triple.centroid),
                ]
            )

        write_row([])
        write_row([labels.max_error, _n4(data.max_error)])
        write_row([labels.experts, str(data.num_experts)])
        decision = _decision(data, labels)
        if decision is not None:
            write_row([labels.likert_decision, decision])

        return buffer.getvalue().encode("utf-8-sig")


class PdfResultRenderer(ResultRenderer):
    """Serialize result data as a formatted A4 PDF report with the chart."""

    media_type = "application/pdf"
    extension = "pdf"

    def __init__(self, palette: ExportPalette):
        """Build a renderer that draws in one theme's colours.

        Fonts are registered here rather than in :meth:`render`, so that every
        method of a constructed renderer works. They used to be registered on the
        way into ``render``, which left the pieces it calls depending on having
        been reached through it: ``<b>`` markup asks reportlab for the bold face of
        a family, and without the family registered that raises rather than falling
        back. It only ever worked because something else happened to register them
        first.

        :param palette: Colours to draw with, from :func:`get_palette`.
        """
        register_fonts()
        self._palette = palette

    def _paint_page(self, canvas: Canvas, doc: BaseDocTemplate) -> None:
        """Fill the whole page with the theme's background.

        Left to the viewer, an unpainted page is white, so a dark report would
        arrive as pale text on white -- unreadable, and still not the theme the
        reader asked for.
        """
        width, height = doc.pagesize
        canvas.saveState()
        canvas.setFillColor(self._palette.background)
        canvas.rect(0, 0, width, height, stroke=0, fill=1)
        canvas.restoreState()

    def render(self, data: ResultExportData, labels: ResultLabels) -> bytes:
        """Render the result as a single-page (or paginated) A4 PDF.

        :param data: Assembled result data.
        :param labels: Localized report labels.
        :return: PDF bytes.
        """
        register_fonts()
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
            title=f"{data.project_name} - {labels.report_title}",
        )
        doc.build(
            self._story(data, labels), onFirstPage=self._paint_page, onLaterPages=self._paint_page
        )
        return buffer.getvalue()

    def _story(self, data: ResultExportData, labels: ResultLabels) -> list[object]:
        """Build the ordered list of flowables for the report body."""
        ink = self._palette.foreground
        title_style = ParagraphStyle(
            "title",
            fontName=font_for(data.project_name, FONT_DISPLAY),
            fontSize=18,
            leading=22,
            textColor=ink,
        )
        subtitle_style = ParagraphStyle(
            "subtitle",
            fontName=FONT_SANS,
            fontSize=11,
            textColor=self._palette.subtitle,
            leading=14,
        )
        heading_style = ParagraphStyle(
            "heading",
            # One style serves all three headings, so it must suit all three.
            fontName=font_for(
                labels.results_heading + labels.chart_heading + labels.opinions_heading,
                FONT_DISPLAY,
                fallback=FONT_SANS_BOLD,
            ),
            fontSize=13,
            spaceBefore=8,
            spaceAfter=6,
            leading=16,
            textColor=ink,
        )
        body_style = ParagraphStyle(
            "body", fontName=FONT_SANS, fontSize=10, leading=14, textColor=ink
        )

        story: list[object] = [
            Paragraph(_escape(data.project_name), title_style),
            Paragraph(_escape(labels.report_title), subtitle_style),
            Spacer(1, 10),
        ]
        if data.project_description:
            story.append(
                Paragraph(
                    f"<b>{_escape(labels.description)}:</b> {_escape(data.project_description)}",
                    body_style,
                )
            )
        scale_text = f"{_n2(data.scale_min)} - {_n2(data.scale_max)}"
        if data.scale_unit:
            scale_text = f"{scale_text} {_escape(data.scale_unit)}"
        story.append(Paragraph(f"<b>{_escape(labels.scale)}:</b> {scale_text}", body_style))
        story.append(
            Paragraph(
                f"<b>{_escape(labels.experts)}:</b> {_mono(str(data.num_experts))}", body_style
            )
        )
        generated = data.generated_at.strftime("%Y-%m-%d %H:%M UTC")
        story.append(Paragraph(f"<b>{_escape(labels.generated_at)}:</b> {generated}", body_style))
        story.append(Spacer(1, 12))

        story.append(self._compromise_card(data, labels))
        story.append(Spacer(1, 8))
        story.append(self._confidence_bar(data, labels))
        story.append(Spacer(1, 14))

        story.append(Paragraph(_escape(labels.supporting_calcs), heading_style))
        story.append(self._results_table(data, labels))
        story.append(Spacer(1, 6))
        decision = _decision(data, labels)
        if decision is not None:
            story.append(
                Paragraph(
                    f"<b>{_escape(labels.likert_decision)}:</b> {_escape(decision)}", body_style
                )
            )
        story.append(Spacer(1, 14))

        story.append(Paragraph(_escape(labels.chart_heading), heading_style))
        # The page's order, and the page opens on the landscape: a report that led
        # with the triangle showed a view the reader had probably not looked at.
        story.append(build_landscape_chart(data, labels, self._palette))
        story.append(Spacer(1, 6))
        story.append(build_triangle_chart(data, labels, self._palette))
        story.append(Spacer(1, 6))
        story.append(build_centroid_chart(data, labels, self._palette))
        story.append(Spacer(1, 14))

        story.append(Paragraph(_escape(labels.opinions_heading), heading_style))
        story.append(self._opinions_table(data, labels))
        return story

    def _badge(self, data: ResultExportData, labels: ResultLabels) -> Table:
        """Build the coloured agreement badge, as the page shows it.

        :param data: Assembled result data, for its agreement reading.
        :param labels: Localized report labels.
        :return: A one-cell table filled with that level's colour.
        """
        fill = {
            AgreementLevel.HIGH: self._palette.agreement_high,
            AgreementLevel.MODERATE: self._palette.agreement_moderate,
            AgreementLevel.LOW: self._palette.agreement_low,
        }[data.agreement]
        # The page labels its two badges differently by position: the card's reads
        # "High Confidence", the one beside the Δmax bar reads "High agreement".
        # The report carries one badge, in the card's position, so it takes the
        # card's wording; the second badge would land two centimetres below the
        # first and say the same thing twice.
        text = f"{labels.confidence_levels[data.agreement.value]} {labels.confidence}"
        style = ParagraphStyle(
            "badge",
            fontName=FONT_SANS,
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.white,
        )
        badge = Table([[Paragraph(_escape(text), style)]], colWidths=[130])
        badge.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), fill),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("ROUNDEDCORNERS", [4, 4, 4, 4]),
                ]
            )
        )
        return badge

    def _compromise_card(self, data: ResultExportData, labels: ResultLabels) -> Table:
        """Build the framed block carrying the answer.

        The page gives the compromise a bordered card, a headline-sized figure and a
        coloured verdict, and leaves the mean and median to a collapsed section. A
        report that lists all three as equal table rows loses exactly that: which of
        the three numbers is the answer.

        :param data: Assembled result data.
        :param labels: Localized report labels.
        :return: The card, ready to add to the story.
        """
        ink = self._palette.foreground
        heading = ParagraphStyle(
            "card_heading",
            fontName=font_for(labels.best_compromise, FONT_DISPLAY, fallback=FONT_SANS_BOLD),
            fontSize=15,
            leading=19,
            textColor=ink,
        )
        caption = ParagraphStyle(
            "card_caption",
            fontName=FONT_SANS,
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=self._palette.subtitle,
        )
        figure = ParagraphStyle(
            "card_figure",
            fontName=FONT_MONO,
            fontSize=26,
            leading=30,
            alignment=TA_CENTER,
            textColor=ink,
        )

        centroid = _n2(data.best_compromise.centroid)
        spread = f'<font size="11" color="{self._palette.subtitle.hexval()}"> ± {_n2(data.max_error)}</font>'
        triple = Table(
            [
                [
                    Paragraph(_escape(labels.lower_desc), caption),
                    Paragraph(_escape(labels.peak_desc), caption),
                    Paragraph(_escape(labels.upper_desc), caption),
                ],
                [
                    Paragraph(_n2(data.best_compromise.lower), _mono_centered(ink)),
                    Paragraph(_n2(data.best_compromise.peak), _mono_centered(ink)),
                    Paragraph(_n2(data.best_compromise.upper), _mono_centered(ink)),
                ],
            ],
            colWidths=_thirds(_CONTENT_WIDTH - 2 * _CARD_PADDING),
        )
        triple.setStyle(
            TableStyle(
                [
                    ("LINEABOVE", (0, 0), (-1, 0), 0.5, self._palette.grid),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 2),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )

        card = Table(
            [
                [Paragraph(f"{_escape(labels.best_compromise)}", heading)],
                [Paragraph(_escape(labels.result_value).upper(), caption)],
                [Paragraph(f"{centroid}{spread}", figure)],
                [self._badge(data, labels)],
                [triple],
            ],
            colWidths=[_CONTENT_WIDTH],
        )
        card.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 1.2, ink),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
                    ("ALIGN", (0, 3), (0, 3), "CENTER"),
                ]
            )
        )
        return card

    def _confidence_bar(self, data: ResultExportData, labels: ResultLabels) -> Table:
        """Build the Δmax line: the label, the figure and a filled bar.

        The page draws a progress bar because Δmax on its own says nothing -- it is
        an absolute distance, and only its share of the scale carries meaning. The
        bar is that share, and it is filled in the colour of the verdict.

        :param data: Assembled result data.
        :param labels: Localized report labels.
        :return: A two-column row holding the caption and the bar.
        """
        fill = {
            AgreementLevel.HIGH: self._palette.agreement_high,
            AgreementLevel.MODERATE: self._palette.agreement_moderate,
            AgreementLevel.LOW: self._palette.agreement_low,
        }[data.agreement]
        width = 260.0
        span = data.scale_max - data.scale_min
        share = min(data.max_error / span, 1.0) if span else 0.0

        drawing = Drawing(width, 8)
        drawing.add(Rect(0, 2, width, 4, fillColor=self._palette.grid, strokeColor=None))
        if share > 0:
            drawing.add(Rect(0, 2, width * share, 4, fillColor=fill, strokeColor=None))

        caption = ParagraphStyle(
            "bar_caption",
            fontName=FONT_SANS,
            fontSize=9,
            leading=12,
            textColor=self._palette.foreground,
        )
        text = (
            f"<b>{_escape(labels.max_error)}:</b> {_mono(_n2(data.max_error))}"
            f'<font color="{self._palette.subtitle.hexval()}"> '
            f"({_escape(labels.confidence_share).format(percent=f'{share * 100:.0f}')})</font>"
        )
        row = Table(
            [[Paragraph(text, caption), drawing]],
            colWidths=[_CONTENT_WIDTH - width - 10, width + 10],
        )
        row.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (0, 0), 0),
                    ("RIGHTPADDING", (-1, 0), (-1, 0), 0),
                ]
            )
        )
        return row

    def _table_style(self, numeric_from: int) -> TableStyle:
        """Build the shared report-table style, in this renderer's colours.

        Both tables in the report look the same; only where their numeric columns
        start differs, because the opinions table carries one more text column.
        Keeping one definition means a change to padding or a palette field cannot
        land in one table and be forgotten in the other.

        :param numeric_from: Index of the first right-aligned numeric column.
        :return: Style ready to hand to :meth:`Table.setStyle`.
        """
        return TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_SANS),
                ("FONTNAME", (0, 0), (-1, 0), FONT_SANS_BOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), self._palette.table_header),
                ("TEXTCOLOR", (0, 0), (-1, -1), self._palette.foreground),
                ("GRID", (0, 0), (-1, -1), 0.5, self._palette.grid),
                ("FONTNAME", (numeric_from, 1), (-1, -1), FONT_MONO),
                ("ALIGN", (numeric_from, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )

    def _results_table(self, data: ResultExportData, labels: ResultLabels) -> Table:
        """Build the aggregated-results table (one row per aggregate)."""
        rows = [
            ["", labels.col_lower, labels.col_peak, labels.col_upper, labels.col_centroid],
        ]
        for label, triple in (
            (labels.best_compromise, data.best_compromise),
            (labels.arithmetic_mean, data.arithmetic_mean),
            (labels.median, data.median),
        ):
            rows.append(
                [
                    label,
                    _n2(triple.lower),
                    _n2(triple.peak),
                    _n2(triple.upper),
                    _n2(triple.centroid),
                ]
            )
        table = Table(rows, colWidths=[180, 80, 80, 80, 80])
        table.setStyle(self._table_style(numeric_from=1))
        return table

    def _opinions_table(self, data: ResultExportData, labels: ResultLabels) -> Table:
        """Build the per-expert opinions table.

        Expert names and positions are user-controlled and can be long (up to
        255 chars), so they are wrapped in Paragraphs that flow within the
        column rather than plain strings that would overflow or clip the cell.
        """
        cell_style = ParagraphStyle(
            "opinion_cell",
            fontName=FONT_SANS,
            fontSize=9,
            leading=11,
            textColor=self._palette.foreground,
        )
        header: list[object] = [
            labels.col_expert,
            labels.col_position,
            labels.col_lower,
            labels.col_peak,
            labels.col_upper,
            labels.col_centroid,
        ]
        rows: list[list[object]] = [header]
        for opinion in data.opinions:
            rows.append(
                [
                    Paragraph(_escape(opinion.expert_name), cell_style),
                    Paragraph(_escape(opinion.position), cell_style),
                    _n2(opinion.lower),
                    _n2(opinion.peak),
                    _n2(opinion.upper),
                    _n2(opinion.centroid),
                ]
            )
        table = Table(rows, colWidths=[110, 110, 68, 68, 68, 68])
        table.setStyle(self._table_style(numeric_from=2))
        return table


def get_renderer(export_format: ExportFormat, theme: ReportTheme) -> ResultRenderer:
    """Return the renderer for the requested export format.

    :param export_format: Requested file format.
    :param theme: Theme to draw in; ignored by CSV, which carries no colour.
    :return: A PdfResultRenderer for PDF, otherwise a CsvResultRenderer.
    """
    if export_format == ExportFormat.PDF:
        return PdfResultRenderer(get_palette(theme))
    return CsvResultRenderer()
