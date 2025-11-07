"""
Unit tests for examples.utils.display module.

Tests the step-by-step display functions for BeCoMe calculations.
"""
# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF001

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

    def test_display_step_1_with_three_experts(self, capsys):
        """Test arithmetic mean display with three experts."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(10.0, 20.0, 30.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(15.0, 25.0, 35.0)),
            ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(20.0, 30.0, 40.0)),
        ]
        calculator: BeCoMeCalculator = BeCoMeCalculator()

        mean, mean_centroid = display_step_1_arithmetic_mean(opinions, calculator)
        captured = capsys.readouterr()

        output: str = captured.out

        # Check section header
        assert "STEP 1: Arithmetic Mean" in output

        # Check formula display
        assert "Formula:" in output
        assert "α = (1/M)" in output

        # Check that calculations are shown
        assert "Sum of lower bounds:" in output
        assert "Sum of peaks:" in output
        assert "Sum of upper bounds:" in output

        # Check mean display
        assert "Arithmetic Mean:" in output
        assert "α (lower)" in output
        assert "γ (peak)" in output
        assert "β (upper)" in output

        # Check centroid display
        assert "Mean centroid:" in output

        # Verify returned values
        assert mean.lower_bound == 15.0
        assert mean.peak == 25.0
        assert mean.upper_bound == 35.0
        assert isinstance(mean_centroid, float)

    def test_display_step_1_with_single_expert(self, capsys):
        """Test arithmetic mean display with single expert."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(5.0, 10.0, 15.0))
        ]
        calculator: BeCoMeCalculator = BeCoMeCalculator()

        mean, _ = display_step_1_arithmetic_mean(opinions, calculator)
        captured = capsys.readouterr()

        output: str = captured.out

        assert "STEP 1:" in output
        assert mean.lower_bound == 5.0
        assert mean.peak == 10.0
        assert mean.upper_bound == 15.0


class TestDisplayMedianCalculationDetails:
    """Test cases for display_median_calculation_details function."""

    def test_display_median_odd_number(self, capsys):
        """Test median calculation details for odd number of experts."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(10.0, 20.0, 30.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(15.0, 25.0, 35.0)),
            ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(20.0, 30.0, 40.0)),
        ]

        display_median_calculation_details(opinions, 3, is_likert=False)
        captured = capsys.readouterr()

        output: str = captured.out

        assert "ODD (M=3)" in output
        assert "Median = middle expert" in output
        assert "position 2" in output
        assert "centroid:" in output

    def test_display_median_even_number(self, capsys):
        """Test median calculation details for even number of experts."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(10.0, 20.0, 30.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(15.0, 25.0, 35.0)),
            ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(20.0, 30.0, 40.0)),
            ExpertOpinion(expert_id="E4", opinion=FuzzyTriangleNumber(25.0, 35.0, 45.0)),
        ]

        display_median_calculation_details(opinions, 4, is_likert=False)
        captured = capsys.readouterr()

        output: str = captured.out

        assert "EVEN (M=4)" in output
        assert "Median = average of 2th and 3th experts:" in output
        assert "2th:" in output
        assert "3th:" in output
        assert "centroid:" in output

    def test_display_median_likert_odd(self, capsys):
        """Test median calculation details for Likert scale with odd experts."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(25.0, 25.0, 25.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(50.0, 50.0, 50.0)),
            ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(75.0, 75.0, 75.0)),
        ]

        display_median_calculation_details(opinions, 3, is_likert=True)
        captured = capsys.readouterr()

        output: str = captured.out

        assert "ODD (M=3)" in output
        assert "50" in output  # Middle value

    def test_display_median_likert_even(self, capsys):
        """Test median calculation details for Likert scale with even experts."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(25.0, 25.0, 25.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(50.0, 50.0, 50.0)),
            ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(75.0, 75.0, 75.0)),
            ExpertOpinion(expert_id="E4", opinion=FuzzyTriangleNumber(100.0, 100.0, 100.0)),
        ]

        display_median_calculation_details(opinions, 4, is_likert=True)
        captured = capsys.readouterr()

        output: str = captured.out

        assert "EVEN (M=4)" in output
        assert "50" in output
        assert "75" in output


class TestDisplayStep2Median:
    """Test cases for display_step_2_median function."""

    def test_display_step_2_odd_experts(self, capsys):
        """Test median display with odd number of experts."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(10.0, 20.0, 30.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(15.0, 25.0, 35.0)),
            ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(20.0, 30.0, 40.0)),
        ]
        calculator: BeCoMeCalculator = BeCoMeCalculator()

        median, median_centroid = display_step_2_median(opinions, calculator, is_likert=False)
        captured = capsys.readouterr()

        output: str = captured.out

        # Check section header
        assert "STEP 2: Median" in output

        # Check sorting message
        assert "Sorting experts by centroid" in output

        # Check median display
        assert "Median: Ω" in output
        assert "ρ (lower)" in output
        assert "ω (peak)" in output
        assert "σ (upper)" in output
        assert "from middle expert" in output

        # Check centroid display
        assert "Median centroid:" in output

        # Verify returned values
        assert isinstance(median, FuzzyTriangleNumber)
        assert isinstance(median_centroid, float)

    def test_display_step_2_even_experts(self, capsys):
        """Test median display with even number of experts."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(10.0, 20.0, 30.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(15.0, 25.0, 35.0)),
            ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(20.0, 30.0, 40.0)),
            ExpertOpinion(expert_id="E4", opinion=FuzzyTriangleNumber(25.0, 35.0, 45.0)),
        ]
        calculator: BeCoMeCalculator = BeCoMeCalculator()

        _, _ = display_step_2_median(opinions, calculator, is_likert=False)
        captured = capsys.readouterr()

        output: str = captured.out

        assert "STEP 2:" in output
        assert "ρ (lower)" in output
        assert "ω (peak)" in output
        assert "σ (upper)" in output
        assert "/ 2 =" in output  # Average calculation

    def test_display_step_2_likert_scale(self, capsys):
        """Test median display with Likert scale data."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(25.0, 25.0, 25.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(50.0, 50.0, 50.0)),
            ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(75.0, 75.0, 75.0)),
            ExpertOpinion(expert_id="E4", opinion=FuzzyTriangleNumber(100.0, 100.0, 100.0)),
        ]
        calculator: BeCoMeCalculator = BeCoMeCalculator()

        _, _ = display_step_2_median(opinions, calculator, is_likert=True)
        captured = capsys.readouterr()

        output: str = captured.out

        assert "STEP 2:" in output
        assert "Sorting experts by value (centroid)" in output
        assert "All components" in output
        assert "Median centroid:" in output


class TestDisplayStep3BestCompromise:
    """Test cases for display_step_3_best_compromise function."""

    def test_display_step_3_basic(self, capsys):
        """Test best compromise display with basic values."""
        mean: FuzzyTriangleNumber = FuzzyTriangleNumber(10.0, 20.0, 30.0)
        median: FuzzyTriangleNumber = FuzzyTriangleNumber(15.0, 25.0, 35.0)

        best_compromise, best_centroid = display_step_3_best_compromise(mean, median)
        captured = capsys.readouterr()

        output: str = captured.out

        # Check section header
        assert "STEP 3: Best Compromise" in output

        # Check formula
        assert "Formula:" in output
        assert "π = (α + ρ)/2" in output
        assert "φ = (γ + ω)/2" in output
        assert "ξ = (β + σ)/2" in output

        # Check calculations
        assert "π (lower)" in output
        assert "φ (peak)" in output
        assert "ξ (upper)" in output

        # Check best compromise display
        assert "Best Compromise: ΓΩMean" in output
        assert "Best compromise centroid:" in output

        # Verify returned values
        assert best_compromise.lower_bound == 12.5
        assert best_compromise.peak == 22.5
        assert best_compromise.upper_bound == 32.5
        assert isinstance(best_centroid, float)

    def test_display_step_3_equal_values(self, capsys):
        """Test best compromise when mean equals median."""
        fuzzy_num: FuzzyTriangleNumber = FuzzyTriangleNumber(20.0, 30.0, 40.0)

        best_compromise, _ = display_step_3_best_compromise(fuzzy_num, fuzzy_num)
        captured = capsys.readouterr()

        output: str = captured.out

        assert "STEP 3:" in output
        # When mean = median, best_compromise should equal them
        assert best_compromise == fuzzy_num


class TestDisplayStep4MaxError:
    """Test cases for display_step_4_max_error function."""

    def test_display_step_4_basic(self, capsys):
        """Test max error display with basic values."""
        mean_centroid: float = 20.0
        median_centroid: float = 25.0

        max_error: float = display_step_4_max_error(mean_centroid, median_centroid)
        captured = capsys.readouterr()

        output: str = captured.out

        # Check section header
        assert "STEP 4: Maximum Error" in output

        # Check formula
        assert "Formula:" in output
        assert "Δmax = |centroid(Γ) - centroid(Ω)| / 2" in output

        # Check precision indicator message
        assert "precision indicator" in output
        assert "lower is better" in output

        # Check calculations
        assert "Mean centroid" in output
        assert "Median centroid" in output
        assert "Δmax" in output

        # Verify returned value
        assert max_error == 2.5

    def test_display_step_4_zero_error(self, capsys):
        """Test max error display when mean and median centroids are equal."""
        mean_centroid: float = 30.0
        median_centroid: float = 30.0

        max_error: float = display_step_4_max_error(mean_centroid, median_centroid)
        captured = capsys.readouterr()

        output: str = captured.out

        assert "STEP 4:" in output
        assert max_error == 0.0
        assert "0.00" in output

    def test_display_step_4_negative_difference(self, capsys):
        """Test max error when median centroid is less than mean centroid."""
        mean_centroid: float = 50.0
        median_centroid: float = 40.0

        max_error: float = display_step_4_max_error(mean_centroid, median_centroid)
        captured = capsys.readouterr()

        output: str = captured.out

        assert "STEP 4:" in output
        # Absolute value should be used
        assert max_error == 5.0


class TestDisplayIntegration:
    """Integration tests for display functions working together."""

    def test_complete_display_flow(self, capsys):
        """Test complete display flow through all steps."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(10.0, 20.0, 30.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(15.0, 25.0, 35.0)),
            ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(20.0, 30.0, 40.0)),
        ]
        calculator: BeCoMeCalculator = BeCoMeCalculator()

        # Step 1
        mean, mean_centroid = display_step_1_arithmetic_mean(opinions, calculator)

        # Step 2
        median, median_centroid = display_step_2_median(opinions, calculator)

        # Step 3
        best_compromise, _ = display_step_3_best_compromise(mean, median)

        # Step 4
        max_error: float = display_step_4_max_error(mean_centroid, median_centroid)

        captured = capsys.readouterr()
        output: str = captured.out

        # Verify all steps are present
        assert "STEP 1:" in output
        assert "STEP 2:" in output
        assert "STEP 3:" in output
        assert "STEP 4:" in output

        # Verify all results are valid
        assert isinstance(mean, FuzzyTriangleNumber)
        assert isinstance(median, FuzzyTriangleNumber)
        assert isinstance(best_compromise, FuzzyTriangleNumber)
        assert isinstance(max_error, float)
