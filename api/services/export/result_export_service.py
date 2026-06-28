"""Assemble and render a project's BeCoMe result as a downloadable file."""

import logging
import re
from uuid import UUID

from sqlmodel import select

from api.db.models import CalculationResult, Project, User
from api.db.utils import utc_now
from api.services.base import BaseService
from api.services.export.data import (
    ExportedFile,
    ExportFormat,
    FuzzyTriple,
    OpinionRow,
    ReportLang,
    ResultExportData,
)
from api.services.export.labels import get_labels
from api.services.export.renderers import get_renderer
from api.services.opinion_service import OpinionService

logger = logging.getLogger("api.service.result_export")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


class ResultExportService(BaseService):
    """Render a project's cached calculation result as PDF or CSV.

    Loading mirrors the GDPR export's join discipline: the result is one query
    and the opinions (with their users) are one joined query, so an export never
    lazy-loads relationships per row.
    """

    def export(
        self, project: Project, export_format: ExportFormat, lang: ReportLang
    ) -> ExportedFile | None:
        """Render the project's result, or None when nothing is computed yet.

        :param project: Project the caller is already authorized to read.
        :param export_format: Requested file format (PDF or CSV).
        :param lang: Report language.
        :return: The rendered file, or None when the project has no result.
        """
        result = self._get_result(project.id)
        if result is None:
            return None
        data = self._assemble(project, result)
        renderer = get_renderer(export_format)
        content = renderer.render(data, get_labels(lang))
        filename = f"{self._slug(project.name)}-results.{renderer.extension}"
        logger.info(
            "Result export generated",
            extra={
                "event": "result_export_generated",
                "project_id": str(project.id),
                "format": export_format.value,
                "num_experts": data.num_experts,
            },
        )
        return ExportedFile(content=content, media_type=renderer.media_type, filename=filename)

    def _get_result(self, project_id: UUID) -> CalculationResult | None:
        """Load the cached calculation result for a project, if any."""
        statement = select(CalculationResult).where(CalculationResult.project_id == project_id)
        return self._session.exec(statement).first()

    def _assemble(self, project: Project, result: CalculationResult) -> ResultExportData:
        """Build the render-ready data structure from ORM rows."""
        opinions = OpinionService(self._session).get_opinions_for_project(project.id)
        rows = tuple(
            OpinionRow(
                expert_name=self._full_name(item.user),
                position=item.opinion.position,
                lower=item.opinion.lower_bound,
                peak=item.opinion.peak,
                upper=item.opinion.upper_bound,
            )
            for item in opinions
        )
        return ResultExportData(
            project_name=project.name,
            project_description=project.description,
            scale_min=project.scale_min,
            scale_max=project.scale_max,
            scale_unit=project.scale_unit,
            generated_at=utc_now(),
            num_experts=result.num_experts,
            max_error=result.max_error,
            best_compromise=FuzzyTriple(
                result.best_compromise_lower,
                result.best_compromise_peak,
                result.best_compromise_upper,
            ),
            arithmetic_mean=FuzzyTriple(
                result.arithmetic_mean_lower,
                result.arithmetic_mean_peak,
                result.arithmetic_mean_upper,
            ),
            median=FuzzyTriple(result.median_lower, result.median_peak, result.median_upper),
            likert_value=result.likert_value,
            likert_decision=result.likert_decision,
            opinions=rows,
        )

    @staticmethod
    def _full_name(user: User) -> str:
        """Return the expert's display name from their profile."""
        return f"{user.first_name} {user.last_name}".strip()

    @staticmethod
    def _slug(name: str) -> str:
        """Turn a project name into an ASCII, filename-safe slug."""
        slug = _SLUG_RE.sub("-", name.lower()).strip("-")
        return slug or "project"
