"""Unit tests for examples.utils.display module."""
# ruff: noqa: RUF001

import pytest

from examples.utils.display import (
    display_median_calculation_details,
    display_step_1_arithmetic_mean,
    display_step_2_median,
    display_step_3_best_compromise,
    display_step_4_max_error,
)
from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


class TestDisplayStep1ArithmeticMean:
    """Test cases for display_step_1_arithmetic_mean function."""

    def test_display_step_1_output_and_calculation(
        self, capsys, sample_three_opinions: list[ExpertOpinion], calculator: BeCoMeCalculator
    ) -> None:
        """Test arithmetic mean display output format and calculation correctness."""
        # WHEN
        mean, mean_centroid = display_step_1_arithmetic_mean(sample_three_opinions, calculator)
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN
        assert "STEP 1: Arithmetic Mean" in output
        assert "Formula:" in output
        assert "α = (1/M)" in output
        assert "Arithmetic Mean:" in output
        assert "Mean centroid:" in output

        assert mean.lower_bound == 15.0
        assert mean.peak == 25.0
        assert mean.upper_bound == 35.0
        assert isinstance(mean_centroid, float)


class TestDisplayMedianCalculationDetails:
    """Test cases for display_median_calculation_details function."""

    @pytest.mark.parametrize(
        "num_experts,is_likert,expected_in_output",
        [
            (3, False, ["ODD (M=3)", "Median = middle expert", "position 2"]),
            (4, False, ["EVEN (M=4)", "Median = average of 2th and 3th experts:"]),
            (3, True, ["ODD (M=3)", "50"]),  # Likert with odd experts
            (4, True, ["EVEN (M=4)", "50", "75"]),  # Likert with even experts
        ],
    )
    def test_display_median_calculation_details(
        self,
        capsys,
        opinions_factory,
        num_experts: int,
        is_likert: bool,
        expected_in_output: list[str],
    ) -> None:
        """Test median calculation details for different expert counts and data types."""
        # GIVEN
        opinions: list[ExpertOpinion] = opinions_factory(num_experts, is_likert)

        # WHEN
        display_median_calculation_details(opinions, num_experts, is_likert=is_likert)
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN
        for expected in expected_in_output:
            assert expected in output


class TestDisplayStep2Median:
    """Test cases for display_step_2_median function."""

    @pytest.mark.parametrize(
        "num_experts,is_likert,expected_in_output",
        [
            (3, False, ["STEP 2: Median", "Sorting experts by centroid", "from middle expert"]),
            (4, False, ["STEP 2:", "/ 2 ="]),  # Even experts shows average calculation
            (4, True, ["STEP 2:", "Sorting experts by value (centroid)", "All components"]),
        ],
    )
    def test_display_step_2_output(
        self,
        capsys,
        opinions_factory,
        calculator: BeCoMeCalculator,
        num_experts: int,
        is_likert: bool,
        expected_in_output: list[str],
    ) -> None:
        """Test median display with different expert counts and data types."""
        # GIVEN
        opinions: list[ExpertOpinion] = opinions_factory(num_experts, is_likert)

        # WHEN
        median, median_centroid = display_step_2_median(opinions, calculator, is_likert=is_likert)
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN
        for expected in expected_in_output:
            assert expected in output

        assert isinstance(median, FuzzyTriangleNumber)
        assert isinstance(median_centroid, float)


class TestDisplayStep3BestCompromise:
    """Test cases for display_step_3_best_compromise function."""

    def test_display_step_3_output_and_calculation(self, capsys) -> None:
        """Test best compromise display output format and calculation correctness."""
        # GIVEN
        mean: FuzzyTriangleNumber = FuzzyTriangleNumber(10.0, 20.0, 30.0)
        median: FuzzyTriangleNumber = FuzzyTriangleNumber(15.0, 25.0, 35.0)

        # WHEN
        best_compromise, best_centroid = display_step_3_best_compromise(mean, median)
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN
        assert "STEP 3: Best Compromise" in output
        assert "Formula:" in output
        assert "π = (α + ρ)/2" in output
        assert "Best Compromise: ΓΩMean" in output
        assert "Best compromise centroid:" in output

        assert best_compromise.lower_bound == 12.5
        assert best_compromise.peak == 22.5
        assert best_compromise.upper_bound == 32.5
        assert isinstance(best_centroid, float)


class TestDisplayStep4MaxError:
    """Test cases for display_step_4_max_error function."""

    @pytest.mark.parametrize(
        "mean_centroid,median_centroid,expected_max_error",
        [
            (20.0, 25.0, 2.5),  # Basic case
            (30.0, 30.0, 0.0),  # Zero error (equal centroids)
            (50.0, 40.0, 5.0),  # Negative difference (absolute value)
        ],
    )
    def test_display_step_4_calculation(
        self, capsys, mean_centroid: float, median_centroid: float, expected_max_error: float
    ) -> None:
        """Test max error display and calculation for various centroid pairs."""
        # WHEN
        max_error: float = display_step_4_max_error(mean_centroid, median_centroid)
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN
        assert "STEP 4: Maximum Error" in output
        assert "Formula:" in output
        assert "Δmax = |centroid(Γ) - centroid(Ω)| / 2" in output
        assert "precision indicator" in output

        assert max_error == expected_max_error


class TestDisplayErrorHandling:
    """Test error handling in display functions."""

    def test_display_step_1_with_none_opinions_raises_error(
        self, calculator: BeCoMeCalculator
    ) -> None:
        """Test that None opinions raise EmptyOpinionsError."""
        # WHEN/THEN
        from src.exceptions import EmptyOpinionsError

        with pytest.raises(EmptyOpinionsError):
            display_step_1_arithmetic_mean(None, calculator)  # type: ignore

    def test_display_step_1_with_none_calculator_raises_error(
        self, sample_three_opinions: list[ExpertOpinion]
    ) -> None:
        """Test that None calculator raises AttributeError."""
        # WHEN/THEN
        with pytest.raises(AttributeError):
            display_step_1_arithmetic_mean(sample_three_opinions, None)  # type: ignore

    def test_display_step_2_with_none_opinions_raises_error(
        self, calculator: BeCoMeCalculator
    ) -> None:
        """Test that None opinions raise TypeError in step 2."""
        # WHEN/THEN
        with pytest.raises(TypeError):
            display_step_2_median(None, calculator)  # type: ignore

    def test_display_step_3_with_none_mean_raises_error(self) -> None:
        """Test that None mean raises AttributeError in step 3."""
        # GIVEN
        median: FuzzyTriangleNumber = FuzzyTriangleNumber(15.0, 25.0, 35.0)

        # WHEN/THEN
        with pytest.raises(AttributeError):
            display_step_3_best_compromise(None, median)  # type: ignore

    def test_display_step_3_with_none_median_raises_error(self) -> None:
        """Test that None median raises AttributeError in step 3."""
        # GIVEN
        mean: FuzzyTriangleNumber = FuzzyTriangleNumber(10.0, 20.0, 30.0)

        # WHEN/THEN
        with pytest.raises(AttributeError):
            display_step_3_best_compromise(mean, None)  # type: ignore
