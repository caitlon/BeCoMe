"""Unit tests for the result-export renderers and service."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from api.db.models import CalculationResult, ExpertOpinion, Project, User
from api.services.export.data import (
    ExportFormat,
    FuzzyTriple,
    OpinionRow,
    ReportLang,
    ResultExportData,
)
from api.services.export.labels import get_labels
from api.services.export.renderers import (
    CsvResultRenderer,
    PdfResultRenderer,
    get_renderer,
)
from api.services.export.result_export_service import ResultExportService


@pytest.fixture
def export_data() -> ResultExportData:
    """A fully populated result data structure for renderer tests."""
    return ResultExportData(
        project_name="Floods 2021",
        project_description="Flood prevention",
        scale_min=0.0,
        scale_max=100.0,
        scale_unit="points",
        generated_at=datetime(2026, 6, 28, 12, 0, tzinfo=UTC),
        num_experts=2,
        max_error=3.5,
        best_compromise=FuzzyTriple(10.0, 20.0, 30.0),
        arithmetic_mean=FuzzyTriple(9.0, 19.0, 29.0),
        median=FuzzyTriple(11.0, 21.0, 31.0),
        likert_value=25,
        likert_decision="Rather disagree",
        opinions=(
            OpinionRow("Alice Smith", "Analyst", 10.0, 20.0, 30.0),
            OpinionRow("Bob Jones", "Lead", 12.0, 22.0, 32.0),
        ),
    )


class TestCsvResultRenderer:
    """Tests for the CSV renderer."""

    def test_render_contains_opinions_and_summary(self, export_data: ResultExportData):
        """The CSV carries the opinions table and the aggregated summary."""
        content = CsvResultRenderer().render(export_data, get_labels(ReportLang.EN))
        text = content.decode("utf-8-sig")
        assert "Expert" in text
        assert "Centroid" in text
        assert "Alice Smith" in text
        assert "Analyst" in text
        assert "Aggregated results" in text
        assert "Rather disagree" in text

    def test_render_uses_czech_labels(self, export_data: ResultExportData):
        """Requesting Czech localizes both the headers and the Likert decision."""
        text = (
            CsvResultRenderer().render(export_data, get_labels(ReportLang.CS)).decode("utf-8-sig")
        )
        assert "Pozice" in text
        assert "Těžiště" in text
        assert "Spíše nesouhlasím" in text

    def test_render_starts_with_utf8_bom(self, export_data: ResultExportData):
        """The CSV opens with a UTF-8 BOM so spreadsheets detect the encoding."""
        content = CsvResultRenderer().render(export_data, get_labels(ReportLang.EN))
        assert content.startswith(b"\xef\xbb\xbf")

    def test_render_neutralizes_formula_injection(self):
        """Expert text starting with a formula trigger is quoted as inert text."""
        data = ResultExportData(
            project_name="P",
            project_description=None,
            scale_min=0.0,
            scale_max=100.0,
            scale_unit="",
            generated_at=datetime(2026, 6, 28, tzinfo=UTC),
            num_experts=1,
            max_error=1.0,
            best_compromise=FuzzyTriple(1.0, 2.0, 3.0),
            arithmetic_mean=FuzzyTriple(1.0, 2.0, 3.0),
            median=FuzzyTriple(1.0, 2.0, 3.0),
            likert_value=None,
            likert_decision=None,
            opinions=(OpinionRow("=HYPERLINK(1)", "@evil", 1.0, 2.0, 3.0),),
        )

        text = CsvResultRenderer().render(data, get_labels(ReportLang.EN)).decode("utf-8-sig")

        assert "'=HYPERLINK(1)" in text
        assert "'@evil" in text


class TestPdfResultRenderer:
    """Tests for the PDF renderer."""

    def test_render_returns_pdf_bytes(self, export_data: ResultExportData):
        """The PDF renderer produces a non-trivial PDF document."""
        content = PdfResultRenderer().render(export_data, get_labels(ReportLang.EN))
        assert content.startswith(b"%PDF")
        assert len(content) > 1000

    def test_render_czech_without_likert_or_description(self, export_data: ResultExportData):
        """A Czech report without optional fields still renders without error."""
        data = replace(
            export_data, likert_value=None, likert_decision=None, project_description=None
        )
        content = PdfResultRenderer().render(data, get_labels(ReportLang.CS))
        assert content.startswith(b"%PDF")


class TestRendererFactory:
    """Tests for the renderer factory."""

    def test_returns_pdf_renderer(self):
        """PDF maps to the PDF renderer."""
        assert isinstance(get_renderer(ExportFormat.PDF), PdfResultRenderer)

    def test_returns_csv_renderer(self):
        """CSV maps to the CSV renderer."""
        assert isinstance(get_renderer(ExportFormat.CSV), CsvResultRenderer)


class TestResultExportServiceHelpers:
    """Tests for the service's filename and naming helpers."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Floods 2021!", "floods-2021"),
            ("  Budget  Case  ", "budget-case"),
            ("Povodně", "povodn"),
            ("***", "project"),
            ("", "project"),
        ],
    )
    def test_slug(self, name: str, expected: str):
        """Project names become ASCII, filename-safe slugs."""
        assert ResultExportService._slug(name) == expected

    def test_full_name(self):
        """The expert display name joins first and last name."""
        user = User(
            id=uuid4(),
            email="a@example.com",
            hashed_password="h",
            first_name="Alice",
            last_name="Smith",
        )
        assert ResultExportService._full_name(user) == "Alice Smith"


def _project() -> Project:
    """A Likert-scaled project for service tests."""
    return Project(id=uuid4(), name="Budget 2026", admin_id=uuid4(), scale_min=0.0, scale_max=100.0)


def _calc_result(project_id) -> CalculationResult:
    """A cached calculation result for the given project."""
    return CalculationResult(
        id=uuid4(),
        project_id=project_id,
        best_compromise_lower=10.0,
        best_compromise_peak=20.0,
        best_compromise_upper=30.0,
        arithmetic_mean_lower=10.0,
        arithmetic_mean_peak=20.0,
        arithmetic_mean_upper=30.0,
        median_lower=10.0,
        median_peak=20.0,
        median_upper=30.0,
        max_error=2.0,
        num_experts=1,
        likert_value=50,
        likert_decision="Neutral",
    )


def _opinion(project_id, user_id) -> ExpertOpinion:
    """An opinion submitted to the given project."""
    return ExpertOpinion(
        id=uuid4(),
        project_id=project_id,
        user_id=user_id,
        position="Analyst",
        lower_bound=10.0,
        peak=20.0,
        upper_bound=30.0,
    )


def _user() -> User:
    """An expert user."""
    return User(
        id=uuid4(),
        email="expert@example.com",
        hashed_password="h",
        first_name="Al",
        last_name="Pal",
    )


class TestResultExportServiceExport:
    """Tests for ResultExportService.export with a mocked session."""

    def test_returns_none_when_no_result(self):
        """Exporting a project without a cached result yields None."""
        session = MagicMock()
        query = MagicMock()
        query.first.return_value = None
        session.exec.return_value = query

        exported = ResultExportService(session).export(_project(), ExportFormat.CSV, ReportLang.EN)

        assert exported is None

    def test_builds_csv_export_file(self):
        """A populated project renders a named CSV attachment."""
        project = _project()
        user = _user()
        result_query = MagicMock()
        result_query.first.return_value = _calc_result(project.id)
        opinions_query = MagicMock()
        opinions_query.all.return_value = [(_opinion(project.id, user.id), user)]
        session = MagicMock()
        session.exec.side_effect = [result_query, opinions_query]

        exported = ResultExportService(session).export(project, ExportFormat.CSV, ReportLang.EN)

        assert exported is not None
        assert exported.media_type == "text/csv"
        assert exported.filename == "budget-2026-results.csv"
        assert b"Analyst" in exported.content

    def test_logs_generation_event(self):
        """A business log records the export tagged with its event name."""
        project = _project()
        user = _user()
        result_query = MagicMock()
        result_query.first.return_value = _calc_result(project.id)
        opinions_query = MagicMock()
        opinions_query.all.return_value = [(_opinion(project.id, user.id), user)]
        session = MagicMock()
        session.exec.side_effect = [result_query, opinions_query]

        with patch("api.services.export.result_export_service.logger") as mock_logger:
            ResultExportService(session).export(project, ExportFormat.PDF, ReportLang.EN)

        assert mock_logger.info.call_args[1]["extra"]["event"] == "result_export_generated"
