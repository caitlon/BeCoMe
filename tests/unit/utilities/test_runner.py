"""Unit tests for examples.utils.runner module."""

import dataclasses
from pathlib import Path

import pytest

from examples.utils.locales import CS_DISPLAY, CS_FORMATTING, EN_DISPLAY, EN_FORMATTING
from examples.utils.runner import AnalysisResult, run_analysis
from src.models.fuzzy_number import FuzzyTriangleNumber

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "examples" / "data"


class TestAnalysisResultImmutability:
    """Test that AnalysisResult is a frozen dataclass."""

    def test_cannot_modify_field(self) -> None:
        """Test that assigning to a field raises FrozenInstanceError."""
        # GIVEN
        result = AnalysisResult(
            opinions=[],
            metadata={},
            mean=FuzzyTriangleNumber(1.0, 2.0, 3.0),
            mean_centroid=2.0,
            median=FuzzyTriangleNumber(1.0, 2.0, 3.0),
            median_centroid=2.0,
            best_compromise=FuzzyTriangleNumber(1.0, 2.0, 3.0),
            best_compromise_centroid=2.0,
            max_error=0.0,
        )

        # WHEN/THEN
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.max_error = 999.0  # type: ignore[misc]


class TestRunAnalysisWithEnglish:
    """Test run_analysis with English labels on real data files."""

    def test_budget_case(self) -> None:
        """Test analysis of budget case returns correct structure."""
        # GIVEN
        data_file = str(DATA_DIR / "en" / "budget_case.txt")

        # WHEN
        result = run_analysis(
            data_file=data_file,
            case_title="BUDGET CASE",
            display_labels=EN_DISPLAY,
            formatting_labels=EN_FORMATTING,
        )

        # THEN
        assert len(result.opinions) == 22
        assert result.metadata["case"] == "Budget"
        assert isinstance(result.mean, FuzzyTriangleNumber)
        assert isinstance(result.median, FuzzyTriangleNumber)
        assert isinstance(result.best_compromise, FuzzyTriangleNumber)
        assert result.max_error >= 0.0

    def test_floods_case(self) -> None:
        """Test analysis of floods case returns correct structure."""
        # GIVEN
        data_file = str(DATA_DIR / "en" / "floods_case.txt")

        # WHEN
        result = run_analysis(
            data_file=data_file,
            case_title="FLOODS CASE",
            display_labels=EN_DISPLAY,
            formatting_labels=EN_FORMATTING,
        )

        # THEN
        assert len(result.opinions) == 13
        assert isinstance(result.best_compromise, FuzzyTriangleNumber)
        assert result.max_error >= 0.0


class TestRunAnalysisWithCzech:
    """Test run_analysis with Czech labels."""

    def test_czech_budget_case(self) -> None:
        """Test analysis with Czech labels produces valid results."""
        # GIVEN
        data_file = str(DATA_DIR / "cs" / "budget_case.txt")

        # WHEN
        result = run_analysis(
            data_file=data_file,
            case_title="PŘÍPAD ROZPOČET",
            display_labels=CS_DISPLAY,
            formatting_labels=CS_FORMATTING,
        )

        # THEN
        assert len(result.opinions) == 22
        assert isinstance(result.best_compromise, FuzzyTriangleNumber)
        assert result.best_compromise_centroid > 0.0


class TestRunAnalysisLikert:
    """Test run_analysis with Likert scale data."""

    def test_pendlers_case_is_likert(self) -> None:
        """Test analysis of Likert scale pendlers case."""
        # GIVEN
        data_file = str(DATA_DIR / "en" / "pendlers_case.txt")

        # WHEN
        result = run_analysis(
            data_file=data_file,
            case_title="PENDLERS CASE",
            display_labels=EN_DISPLAY,
            formatting_labels=EN_FORMATTING,
            is_likert=True,
        )

        # THEN
        assert len(result.opinions) == 22
        assert isinstance(result.best_compromise, FuzzyTriangleNumber)
        assert result.max_error >= 0.0


class TestRunAnalysisConsistency:
    """Test that run_analysis results are mathematically consistent."""

    def test_best_compromise_is_average_of_mean_and_median(self) -> None:
        """Test that best_compromise = (mean + median) / 2 component-wise."""
        # GIVEN
        data_file = str(DATA_DIR / "en" / "budget_case.txt")

        # WHEN
        result = run_analysis(
            data_file=data_file,
            case_title="BUDGET CASE",
            display_labels=EN_DISPLAY,
            formatting_labels=EN_FORMATTING,
        )

        # THEN
        expected_lower = (result.mean.lower_bound + result.median.lower_bound) / 2
        expected_peak = (result.mean.peak + result.median.peak) / 2
        expected_upper = (result.mean.upper_bound + result.median.upper_bound) / 2

        assert result.best_compromise.lower_bound == pytest.approx(expected_lower)
        assert result.best_compromise.peak == pytest.approx(expected_peak)
        assert result.best_compromise.upper_bound == pytest.approx(expected_upper)

    def test_max_error_formula(self) -> None:
        """Test that max_error = |mean_centroid - median_centroid| / 2."""
        # GIVEN
        data_file = str(DATA_DIR / "en" / "floods_case.txt")

        # WHEN
        result = run_analysis(
            data_file=data_file,
            case_title="FLOODS CASE",
            display_labels=EN_DISPLAY,
            formatting_labels=EN_FORMATTING,
        )

        # THEN
        expected = abs(result.mean_centroid - result.median_centroid) / 2
        assert result.max_error == pytest.approx(expected)

    def test_centroid_formula(self) -> None:
        """Test that centroids are (lower + peak + upper) / 3."""
        # GIVEN
        data_file = str(DATA_DIR / "en" / "budget_case.txt")

        # WHEN
        result = run_analysis(
            data_file=data_file,
            case_title="BUDGET CASE",
            display_labels=EN_DISPLAY,
            formatting_labels=EN_FORMATTING,
        )

        # THEN
        mean = result.mean
        expected_centroid = (mean.lower_bound + mean.peak + mean.upper_bound) / 3
        assert result.mean_centroid == pytest.approx(expected_centroid)
