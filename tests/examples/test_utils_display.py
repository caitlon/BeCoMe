"""
Unit tests for examples.utils.display module.

Tests the step-by-step display functions for BeCoMe calculations.

Following Lott's "Python Object-Oriented Programming" (Chapter 13):
- Tests structured as GIVEN-WHEN-THEN
- Fixtures provide test data (Dependency Injection)
- Each test validates a single behavior
- capsys fixture used to test console output
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

    def test_display_step_1_output_and_calculation(
        self, capsys, sample_three_opinions: list[ExpertOpinion], calculator: BeCoMeCalculator
    ) -> None:
        """
        Test arithmetic mean display output format and calculation correctness.

        GIVEN: Three expert opinions and calculator
        WHEN: Displaying step 1 arithmetic mean calculation
        THEN: Output contains expected sections and calculation is correct
        """
        # GIVEN: sample_three_opinions and calculator fixtures provide test data

        # WHEN: Display step 1 arithmetic mean
        mean, mean_centroid = display_step_1_arithmetic_mean(sample_three_opinions, calculator)
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN: Output contains all expected sections
        assert "STEP 1: Arithmetic Mean" in output
        assert "Formula:" in output
        assert "α = (1/M)" in output
        assert "Arithmetic Mean:" in output
        assert "Mean centroid:" in output

        # THEN: Calculation is correct (mean of 10-20-30, 15-25-35, 20-30-40)
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
    ) -> None:
        """
        Test median calculation details for different expert counts and data types.

        GIVEN: Expert opinions (fuzzy or Likert scale) with odd or even count
        WHEN: Displaying median calculation details
        THEN: Output shows correct formula and calculation based on expert count parity
        """
        # GIVEN: Create opinions based on is_likert and num_experts
        if is_likert:
            values = [25.0 * (i + 1) for i in range(num_experts)]
            opinions: list[ExpertOpinion] = [
                ExpertOpinion(expert_id=f"E{i + 1}", opinion=FuzzyTriangleNumber(v, v, v))
                for i, v in enumerate(values)
            ]
        else:
            opinions: list[ExpertOpinion] = [
                ExpertOpinion(
                    expert_id=f"E{i + 1}",
                    opinion=FuzzyTriangleNumber(10.0 * (i + 1), 20.0 * (i + 1), 30.0 * (i + 1)),
                )
                for i in range(num_experts)
            ]

        # WHEN: Display median calculation details
        display_median_calculation_details(opinions, num_experts, is_likert=is_likert)
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN: All expected strings appear in output
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
    ) -> None:
        """
        Test median display with different expert counts and data types.

        GIVEN: Expert opinions (fuzzy or Likert scale) with various counts
        WHEN: Displaying step 2 median calculation
        THEN: Output shows correct sorting and median calculation method
        """
        # GIVEN: Create opinions based on is_likert and num_experts
        if is_likert:
            values = [25.0 * (i + 1) for i in range(num_experts)]
            opinions: list[ExpertOpinion] = [
                ExpertOpinion(expert_id=f"E{i + 1}", opinion=FuzzyTriangleNumber(v, v, v))
                for i, v in enumerate(values)
            ]
        else:
            opinions: list[ExpertOpinion] = [
                ExpertOpinion(
                    expert_id=f"E{i + 1}",
                    opinion=FuzzyTriangleNumber(10.0 * (i + 1), 20.0 * (i + 1), 30.0 * (i + 1)),
                )
                for i in range(num_experts)
            ]

        calculator: BeCoMeCalculator = BeCoMeCalculator()

        # WHEN: Display step 2 median
        median, median_centroid = display_step_2_median(opinions, calculator, is_likert=is_likert)
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN: Expected output strings appear
        for expected in expected_in_output:
            assert expected in output

        # THEN: Returned values are correct types
        assert isinstance(median, FuzzyTriangleNumber)
        assert isinstance(median_centroid, float)


class TestDisplayStep3BestCompromise:
    """Test cases for display_step_3_best_compromise function."""

    def test_display_step_3_output_and_calculation(self, capsys) -> None:
        """
        Test best compromise display output format and calculation correctness.

        GIVEN: Arithmetic mean and median fuzzy numbers
        WHEN: Displaying step 3 best compromise calculation
        THEN: Output shows formula and best compromise is average of mean and median
        """
        # GIVEN: Arithmetic mean and median fuzzy numbers
        mean: FuzzyTriangleNumber = FuzzyTriangleNumber(10.0, 20.0, 30.0)
        median: FuzzyTriangleNumber = FuzzyTriangleNumber(15.0, 25.0, 35.0)

        # WHEN: Display step 3 best compromise
        best_compromise, best_centroid = display_step_3_best_compromise(mean, median)
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN: Output contains expected sections
        assert "STEP 3: Best Compromise" in output
        assert "Formula:" in output
        assert "π = (α + ρ)/2" in output
        assert "Best Compromise: ΓΩMean" in output
        assert "Best compromise centroid:" in output

        # THEN: Best compromise is average of mean and median
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
        """
        Test max error display and calculation for various centroid pairs.

        GIVEN: Mean and median centroid values
        WHEN: Displaying step 4 maximum error calculation
        THEN: Output shows formula and max error is calculated correctly
        """
        # GIVEN: mean_centroid and median_centroid provided by parametrize

        # WHEN: Display step 4 max error
        max_error: float = display_step_4_max_error(mean_centroid, median_centroid)
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN: Output contains expected sections
        assert "STEP 4: Maximum Error" in output
        assert "Formula:" in output
        assert "Δmax = |centroid(Γ) - centroid(Ω)| / 2" in output
        assert "precision indicator" in output

        # THEN: Max error is calculated correctly as |mean - median| / 2
        assert max_error == expected_max_error
