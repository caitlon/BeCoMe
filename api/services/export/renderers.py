"""Renderers that serialize result data into a downloadable CSV or PDF.

The two renderers share a small ``ResultRenderer`` Strategy interface so the
service can pick one by format and stay open for new formats (mirrors the
median-strategy pattern in ``src/calculators``).
"""

import csv
import io
from abc import ABC, abstractmethod

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

from api.services.export.data import ExportFormat, ResultExportData
from api.services.export.fonts import FONT_NAME, FONT_NAME_BOLD, register_fonts
from api.services.export.fuzzy_chart import build_triangle_chart
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


def _escape(text: str) -> str:
    """Escape the XML special characters reportlab Paragraph markup parses."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_CSV_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


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

        :param palette: Colours to draw with, from :func:`get_palette`.
        """
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
            "title", fontName=FONT_NAME_BOLD, fontSize=18, leading=22, textColor=ink
        )
        subtitle_style = ParagraphStyle(
            "subtitle",
            fontName=FONT_NAME,
            fontSize=11,
            textColor=self._palette.subtitle,
            leading=14,
        )
        heading_style = ParagraphStyle(
            "heading",
            fontName=FONT_NAME_BOLD,
            fontSize=13,
            spaceBefore=8,
            spaceAfter=6,
            leading=16,
            textColor=ink,
        )
        body_style = ParagraphStyle(
            "body", fontName=FONT_NAME, fontSize=10, leading=14, textColor=ink
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
        story.append(Paragraph(f"<b>{_escape(labels.experts)}:</b> {data.num_experts}", body_style))
        generated = data.generated_at.strftime("%Y-%m-%d %H:%M UTC")
        story.append(Paragraph(f"<b>{_escape(labels.generated_at)}:</b> {generated}", body_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph(_escape(labels.results_heading), heading_style))
        story.append(self._results_table(data, labels))
        story.append(Spacer(1, 6))
        story.append(
            Paragraph(f"<b>{_escape(labels.max_error)}:</b> {_n2(data.max_error)}", body_style)
        )
        decision = _decision(data, labels)
        if decision is not None:
            story.append(
                Paragraph(
                    f"<b>{_escape(labels.likert_decision)}:</b> {_escape(decision)}", body_style
                )
            )
        story.append(Spacer(1, 14))

        story.append(Paragraph(_escape(labels.chart_heading), heading_style))
        story.append(build_triangle_chart(data, labels, self._palette))
        story.append(Spacer(1, 14))

        story.append(Paragraph(_escape(labels.opinions_heading), heading_style))
        story.append(self._opinions_table(data, labels))
        return story

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
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("FONTNAME", (0, 0), (-1, 0), FONT_NAME_BOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), self._palette.table_header),
                ("TEXTCOLOR", (0, 0), (-1, -1), self._palette.foreground),
                ("GRID", (0, 0), (-1, -1), 0.5, self._palette.grid),
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
            fontName=FONT_NAME,
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
