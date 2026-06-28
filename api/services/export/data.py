"""Plain data structures shared across the result-export renderers.

These types decouple rendering from the database models: a renderer takes a
``ResultExportData`` (built from ORM rows by the service) and never touches the
session, which keeps the PDF/CSV builders trivially unit-testable.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from src.models.fuzzy_number import triangular_centroid


class ExportFormat(StrEnum):
    """File format requested for a result export."""

    PDF = "pdf"
    CSV = "csv"


class ReportLang(StrEnum):
    """Language a rendered report is localized into."""

    EN = "en"
    CS = "cs"


@dataclass(frozen=True, slots=True)
class FuzzyTriple:
    """An aggregated triangular fuzzy number (lower <= peak <= upper)."""

    lower: float
    peak: float
    upper: float

    @property
    def centroid(self) -> float:
        """Return the triangle centroid (lower + peak + upper) / 3.

        :return: Centroid of the triangular fuzzy number.
        """
        return triangular_centroid(self.lower, self.peak, self.upper)


@dataclass(frozen=True, slots=True)
class OpinionRow:
    """A single expert opinion as it appears in an export table."""

    expert_name: str
    position: str
    lower: float
    peak: float
    upper: float

    @property
    def centroid(self) -> float:
        """Return the opinion's triangle centroid.

        :return: Centroid of the opinion's triangular fuzzy number.
        """
        return triangular_centroid(self.lower, self.peak, self.upper)


@dataclass(frozen=True, slots=True)
class ResultExportData:
    """Everything needed to render a project's result as PDF or CSV."""

    project_name: str
    project_description: str | None
    scale_min: float
    scale_max: float
    scale_unit: str
    generated_at: datetime
    num_experts: int
    max_error: float
    best_compromise: FuzzyTriple
    arithmetic_mean: FuzzyTriple
    median: FuzzyTriple
    likert_value: int | None
    likert_decision: str | None
    opinions: tuple[OpinionRow, ...]


@dataclass(frozen=True, slots=True)
class ExportedFile:
    """A rendered export ready to stream to the client."""

    content: bytes
    media_type: str
    filename: str
