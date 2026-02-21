"""Shared analysis runner for BeCoMe case studies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.calculators.become_calculator import BeCoMeCalculator
from src.models.fuzzy_number import FuzzyTriangleNumber

from .data_loading import load_data_from_txt
from .display import (
    display_step_1_arithmetic_mean,
    display_step_2_median,
    display_step_3_best_compromise,
    display_step_4_max_error,
)
from .formatting import display_case_header

if TYPE_CHECKING:
    from src.calculators.base_calculator import BaseAggregationCalculator
    from src.models.expert_opinion import ExpertOpinion

    from .labels import DisplayLabels, FormattingLabels


@dataclass(frozen=True)
class AnalysisResult:
    """Container for BeCoMe analysis step outputs."""

    opinions: list[ExpertOpinion]
    metadata: dict[str, str]
    mean: FuzzyTriangleNumber
    mean_centroid: float
    median: FuzzyTriangleNumber
    median_centroid: float
    best_compromise: FuzzyTriangleNumber
    best_compromise_centroid: float
    max_error: float


def run_analysis(
    data_file: str,
    case_title: str,
    display_labels: DisplayLabels,
    formatting_labels: FormattingLabels,
    calculator: BaseAggregationCalculator | None = None,
    is_likert: bool = False,
) -> AnalysisResult:
    """
    Execute the 4 BeCoMe analysis steps and return results.

    :param data_file: Path to the data file with expert opinions
    :param case_title: Case study title for the header
    :param display_labels: Locale-specific display labels
    :param formatting_labels: Locale-specific formatting labels
    :param calculator: Aggregation calculator. Defaults to BeCoMeCalculator.
    :param is_likert: Whether this is Likert scale data
    :return: AnalysisResult with all intermediate and final values
    """
    if calculator is None:
        calculator = BeCoMeCalculator()

    opinions, metadata = load_data_from_txt(data_file)

    display_case_header(case_title, opinions, metadata, formatting_labels)

    mean, mean_centroid = display_step_1_arithmetic_mean(opinions, calculator, display_labels)

    median, median_centroid = display_step_2_median(
        opinions, calculator, is_likert=is_likert, labels=display_labels
    )

    best_compromise, bc_centroid = display_step_3_best_compromise(mean, median, display_labels)

    max_error = display_step_4_max_error(mean_centroid, median_centroid, display_labels)

    return AnalysisResult(
        opinions=opinions,
        metadata=metadata,
        mean=mean,
        mean_centroid=mean_centroid,
        median=median,
        median_centroid=median_centroid,
        best_compromise=best_compromise,
        best_compromise_centroid=bc_centroid,
        max_error=max_error,
    )
