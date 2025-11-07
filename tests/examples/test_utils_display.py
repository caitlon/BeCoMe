"""
Unit tests for examples.utils.display module.

Tests the step-by-step display functions for BeCoMe calculations.
"""
# ignore ruff rule for mathematical symbols
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

    def test_display_step_1_output_and_calculation(self, capsys):
        """Test arithmetic mean display output format and calculation correctness."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(10.0, 20.0, 30.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(15.0, 25.0, 35.0)),
            ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(20.0, 30.0, 40.0)),
        ]
        calculator: BeCoMeCalculator = BeCoMeCalculator()

        mean, mean_centroid = display_step_1_arithmetic_mean(opinions, calculator)
        captured = capsys.readouterr()

        output: str = captured.out

        # Check output format
        assert "STEP 1: Arithmetic Mean" in output
        assert "Formula:" in output
        assert "α = (1/M)" in output
        assert "Arithmetic Mean:" in output
        assert "Mean centroid:" in output

        # Verify calculation correctness
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
        self, capsys, num_experts: int, is_likert: bool, expected_in_output: list[str]
    ):
        """Test median calculation details for different expert counts and data types."""
        # Create opinions based on is_likert
        if is_likert:
            values = [25.0 * (i + 1) for i in range(num_experts)]
            opinions: list[ExpertOpinion] = [
                ExpertOpinion(expert_id=f"E{i+1}", opinion=FuzzyTriangleNumber(v, v, v))
                for i, v in enumerate(values)
            ]
        else:
            opinions: list[ExpertOpinion] = [
                ExpertOpinion(
                    expert_id=f"E{i+1}",
                    opinion=FuzzyTriangleNumber(10.0 * (i + 1), 20.0 * (i + 1), 30.0 * (i + 1)),
                )
                for i in range(num_experts)
            ]

        display_median_calculation_details(opinions, num_experts, is_likert=is_likert)
        captured = capsys.readouterr()

        output: str = captured.out

        # Check all expected strings are in output
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
        self, capsys, num_experts: int, is_likert: bool, expected_in_output: list[str]
    ):
        """Test median display with different expert counts and data types."""
        # Create opinions based on is_likert
        if is_likert:
            values = [25.0 * (i + 1) for i in range(num_experts)]
            opinions: list[ExpertOpinion] = [
                ExpertOpinion(expert_id=f"E{i+1}", opinion=FuzzyTriangleNumber(v, v, v))
                for i, v in enumerate(values)
            ]
        else:
            opinions: list[ExpertOpinion] = [
                ExpertOpinion(
                    expert_id=f"E{i+1}",
                    opinion=FuzzyTriangleNumber(10.0 * (i + 1), 20.0 * (i + 1), 30.0 * (i + 1)),
                )
                for i in range(num_experts)
            ]

        calculator: BeCoMeCalculator = BeCoMeCalculator()
        median, median_centroid = display_step_2_median(opinions, calculator, is_likert=is_likert)
        captured = capsys.readouterr()

        output: str = captured.out

        # Check expected output
        for expected in expected_in_output:
            assert expected in output

        # Verify returned values
        assert isinstance(median, FuzzyTriangleNumber)
        assert isinstance(median_centroid, float)


class TestDisplayStep3BestCompromise:
    """Test cases for display_step_3_best_compromise function."""

    def test_display_step_3_output_and_calculation(self, capsys):
        """Test best compromise display output format and calculation correctness."""
        mean: FuzzyTriangleNumber = FuzzyTriangleNumber(10.0, 20.0, 30.0)
        median: FuzzyTriangleNumber = FuzzyTriangleNumber(15.0, 25.0, 35.0)

        best_compromise, best_centroid = display_step_3_best_compromise(mean, median)
        captured = capsys.readouterr()

        output: str = captured.out

        # Check output format
        assert "STEP 3: Best Compromise" in output
        assert "Formula:" in output
        assert "π = (α + ρ)/2" in output
        assert "Best Compromise: ΓΩMean" in output
        assert "Best compromise centroid:" in output

        # Verify calculation correctness
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
    ):
        """Test max error display and calculation for various centroid pairs."""
        max_error: float = display_step_4_max_error(mean_centroid, median_centroid)
        captured = capsys.readouterr()

        output: str = captured.out

        # Check output format
        assert "STEP 4: Maximum Error" in output
        assert "Formula:" in output
        assert "Δmax = |centroid(Γ) - centroid(Ω)| / 2" in output
        assert "precision indicator" in output

        # Verify calculation correctness
        assert max_error == expected_max_error
