"""
Unit tests for BeCoMeCalculator class.
"""

import pytest

from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


class TestBeCoMeCalculatorArithmeticMean:
    """Test cases for arithmetic mean calculation."""

    def test_arithmetic_mean_with_three_experts(self):
        """Test arithmetic mean calculation with 3 experts."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=9.0, upper_bound=12.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_arithmetic_mean(opinions)

        # Expected: average of each component
        # Lower: (3 + 6 + 9) / 3 = 6.0
        # Peak: (6 + 9 + 12) / 3 = 9.0
        # Upper: (9 + 12 + 15) / 3 = 12.0
        assert result.lower_bound == 6.0
        assert result.peak == 9.0
        assert result.upper_bound == 12.0

    def test_arithmetic_mean_with_single_expert(self):
        """Test arithmetic mean with single expert returns same values."""
        opinion = ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        )

        calculator = BeCoMeCalculator()
        result = calculator.calculate_arithmetic_mean([opinion])

        # Single expert: mean should equal the expert's opinion
        assert result.lower_bound == 5.0
        assert result.peak == 10.0
        assert result.upper_bound == 15.0

    def test_arithmetic_mean_with_identical_opinions(self):
        """Test arithmetic mean when all experts have identical opinions."""
        identical_opinion = FuzzyTriangleNumber(lower_bound=7.0, peak=10.0, upper_bound=13.0)
        opinions = [ExpertOpinion(expert_id=f"E{i}", opinion=identical_opinion) for i in range(5)]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_arithmetic_mean(opinions)

        # All identical: mean should equal the common value
        assert result.lower_bound == 7.0
        assert result.peak == 10.0
        assert result.upper_bound == 13.0

    def test_arithmetic_mean_with_decimal_values(self):
        """Test arithmetic mean with decimal values."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=2.5, peak=5.5, upper_bound=8.5),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=3.5, peak=6.5, upper_bound=9.5),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_arithmetic_mean(opinions)

        # Lower: (2.5 + 3.5) / 2 = 3.0
        # Peak: (5.5 + 6.5) / 2 = 6.0
        # Upper: (8.5 + 9.5) / 2 = 9.0
        assert result.lower_bound == 3.0
        assert result.peak == 6.0
        assert result.upper_bound == 9.0

    def test_arithmetic_mean_preserves_fuzzy_constraint(self):
        """Test that result maintains lower <= peak <= upper constraint."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=5.0, upper_bound=10.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=2.0, peak=6.0, upper_bound=12.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=7.0, upper_bound=14.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_arithmetic_mean(opinions)

        # Result should maintain constraint
        assert result.lower_bound <= result.peak
        assert result.peak <= result.upper_bound

    def test_arithmetic_mean_empty_list_raises_error(self):
        """Test that empty opinions list raises ValueError."""
        calculator = BeCoMeCalculator()

        with pytest.raises(ValueError) as exc_info:
            calculator.calculate_arithmetic_mean([])

        assert "empty" in str(exc_info.value).lower()

    def test_arithmetic_mean_with_five_experts(self):
        """Test arithmetic mean with 5 experts (odd number)."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=8.0, upper_bound=11.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=9.0, upper_bound=12.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=10.0, upper_bound=13.0),
            ),
            ExpertOpinion(
                expert_id="E4",
                opinion=FuzzyTriangleNumber(lower_bound=8.0, peak=11.0, upper_bound=14.0),
            ),
            ExpertOpinion(
                expert_id="E5",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_arithmetic_mean(opinions)

        # Lower: (5 + 6 + 7 + 8 + 9) / 5 = 7.0
        # Peak: (8 + 9 + 10 + 11 + 12) / 5 = 10.0
        # Upper: (11 + 12 + 13 + 14 + 15) / 5 = 13.0
        assert result.lower_bound == 7.0
        assert result.peak == 10.0
        assert result.upper_bound == 13.0

    def test_arithmetic_mean_component_independence(self):
        """Test that each component is calculated independently."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=10.0, upper_bound=10.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=20.0, peak=30.0, upper_bound=40.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_arithmetic_mean(opinions)

        # Each component averaged independently
        assert result.lower_bound == 15.0  # (10 + 20) / 2
        assert result.peak == 20.0  # (10 + 30) / 2
        assert result.upper_bound == 25.0  # (10 + 40) / 2


class TestBeCoMeCalculatorMedian:
    """Test cases for median calculation."""

    def test_median_with_three_experts_odd(self):
        """Test median with 3 experts (odd) - should return middle element."""
        opinions = [
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
            ),  # centroid = 12.0
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
            ),  # centroid = 6.0
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=9.0, upper_bound=12.0),
            ),  # centroid = 9.0
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_median(opinions)

        # After sorting by centroid: E1 (6.0), E2 (9.0), E3 (12.0)
        # Middle element (index 1): E2
        assert result.lower_bound == 6.0
        assert result.peak == 9.0
        assert result.upper_bound == 12.0

    def test_median_with_five_experts_odd(self):
        """Test median with 5 experts (odd)."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=4.0, peak=5.0, upper_bound=6.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=8.0, upper_bound=9.0),
            ),
            ExpertOpinion(
                expert_id="E4",
                opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=11.0, upper_bound=12.0),
            ),
            ExpertOpinion(
                expert_id="E5",
                opinion=FuzzyTriangleNumber(lower_bound=13.0, peak=14.0, upper_bound=15.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_median(opinions)

        # Middle element (index 2): E3
        assert result.lower_bound == 7.0
        assert result.peak == 8.0
        assert result.upper_bound == 9.0

    def test_median_with_two_experts_even(self):
        """Test median with 2 experts (even) - should average two elements."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=9.0, upper_bound=12.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_median(opinions)

        # Average of two elements
        # Lower: (3 + 6) / 2 = 4.5
        # Peak: (6 + 9) / 2 = 7.5
        # Upper: (9 + 12) / 2 = 10.5
        assert result.lower_bound == 4.5
        assert result.peak == 7.5
        assert result.upper_bound == 10.5

    def test_median_with_four_experts_even(self):
        """Test median with 4 experts (even)."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=4.0, peak=5.0, upper_bound=6.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=8.0, upper_bound=9.0),
            ),
            ExpertOpinion(
                expert_id="E4",
                opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=11.0, upper_bound=12.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_median(opinions)

        # Two middle elements (indices 1 and 2): E2 and E3
        # Lower: (4 + 7) / 2 = 5.5
        # Peak: (5 + 8) / 2 = 6.5
        # Upper: (6 + 9) / 2 = 7.5
        assert result.lower_bound == 5.5
        assert result.peak == 6.5
        assert result.upper_bound == 7.5

    def test_median_with_single_expert(self):
        """Test median with single expert returns same values."""
        opinion = ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        )

        calculator = BeCoMeCalculator()
        result = calculator.calculate_median([opinion])

        # Single expert: median equals the expert's opinion
        assert result.lower_bound == 5.0
        assert result.peak == 10.0
        assert result.upper_bound == 15.0

    def test_median_empty_list_raises_error(self):
        """Test that empty opinions list raises ValueError."""
        calculator = BeCoMeCalculator()

        with pytest.raises(ValueError) as exc_info:
            calculator.calculate_median([])

        assert "empty" in str(exc_info.value).lower()

    def test_median_sorts_by_centroid(self):
        """Test that median correctly sorts opinions by centroid before calculation."""
        opinions = [
            ExpertOpinion(
                expert_id="High",
                opinion=FuzzyTriangleNumber(lower_bound=15.0, peak=18.0, upper_bound=21.0),
            ),  # centroid = 18.0
            ExpertOpinion(
                expert_id="Low",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
            ),  # centroid = 6.0
            ExpertOpinion(
                expert_id="Mid",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
            ),  # centroid = 12.0
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_median(opinions)

        # Should return middle after sorting: Mid
        assert result.lower_bound == 9.0
        assert result.peak == 12.0
        assert result.upper_bound == 15.0

    def test_median_preserves_fuzzy_constraint_odd(self):
        """Test that median result maintains lower <= peak <= upper constraint (odd)."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=5.0, upper_bound=10.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=2.0, peak=6.0, upper_bound=12.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=7.0, upper_bound=14.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_median(opinions)

        # Result should maintain constraint
        assert result.lower_bound <= result.peak
        assert result.peak <= result.upper_bound

    def test_median_preserves_fuzzy_constraint_even(self):
        """Test that median result maintains lower <= peak <= upper constraint (even)."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=5.0, upper_bound=10.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=2.0, peak=6.0, upper_bound=12.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_median(opinions)

        # Result should maintain constraint
        assert result.lower_bound <= result.peak
        assert result.peak <= result.upper_bound

    def test_median_with_seven_experts_odd(self):
        """Test median with 7 experts (larger odd case)."""
        opinions = [
            ExpertOpinion(
                expert_id=f"E{i}",
                opinion=FuzzyTriangleNumber(
                    lower_bound=float(i), peak=float(i + 1), upper_bound=float(i + 2)
                ),
            )
            for i in range(1, 8)
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_median(opinions)

        # Middle element (index 3): E4 with values (4.0, 5.0, 6.0)
        assert result.lower_bound == 4.0
        assert result.peak == 5.0
        assert result.upper_bound == 6.0

    def test_median_with_six_experts_even(self):
        """Test median with 6 experts (larger even case)."""
        opinions = [
            ExpertOpinion(
                expert_id=f"E{i}",
                opinion=FuzzyTriangleNumber(
                    lower_bound=float(i * 2),
                    peak=float(i * 2 + 1),
                    upper_bound=float(i * 2 + 2),
                ),
            )
            for i in range(1, 7)
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_median(opinions)

        # Two middle elements (indices 2 and 3): E3 (6, 7, 8) and E4 (8, 9, 10)
        # Lower: (6 + 8) / 2 = 7.0
        # Peak: (7 + 9) / 2 = 8.0
        # Upper: (8 + 10) / 2 = 9.0
        assert result.lower_bound == 7.0
        assert result.peak == 8.0
        assert result.upper_bound == 9.0


class TestBeCoMeCalculatorCompromise:
    """Test cases for full BeCoMe compromise calculation."""

    def test_compromise_with_three_experts_odd(self):
        """Test full BeCoMe calculation with 3 experts (odd)."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=9.0, upper_bound=12.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_compromise(opinions)

        # Verify result type and structure
        assert result is not None
        assert result.num_experts == 3
        assert result.is_even is False

        # Mean: (3+6+9)/3=6, (6+9+12)/3=9, (9+12+15)/3=12 → (6, 9, 12)
        # Median (odd, middle): (6, 9, 12)
        # Compromise: ((6+6)/2, (9+9)/2, (12+12)/2) = (6, 9, 12)
        # Error: (|6-6|/2, |9-9|/2, |12-12|/2) = (0, 0, 0)
        assert result.arithmetic_mean.lower_bound == 6.0
        assert result.arithmetic_mean.peak == 9.0
        assert result.arithmetic_mean.upper_bound == 12.0

        assert result.median.lower_bound == 6.0
        assert result.median.peak == 9.0
        assert result.median.upper_bound == 12.0

        assert result.best_compromise.lower_bound == 6.0
        assert result.best_compromise.peak == 9.0
        assert result.best_compromise.upper_bound == 12.0

        # Max error is now a scalar (float) - distance between centroids
        assert result.max_error == 0.0

    def test_compromise_with_four_experts_even(self):
        """Test full BeCoMe calculation with 4 experts (even)."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=4.0, peak=5.0, upper_bound=6.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=8.0, upper_bound=9.0),
            ),
            ExpertOpinion(
                expert_id="E4",
                opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=11.0, upper_bound=12.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_compromise(opinions)

        assert result.num_experts == 4
        assert result.is_even is True

        # Mean: (1+4+7+10)/4=5.5, (2+5+8+11)/4=6.5, (3+6+9+12)/4=7.5
        # Median (even): avg of E2 and E3 → (5.5, 6.5, 7.5)
        # Same values, so compromise = (5.5, 6.5, 7.5), error = (0, 0, 0)
        assert result.best_compromise.lower_bound == 5.5
        assert result.best_compromise.peak == 6.5
        assert result.best_compromise.upper_bound == 7.5

        # Max error is now a scalar (float) - distance between centroids
        assert result.max_error == 0.0

    def test_compromise_with_skewed_data(self):
        """Test BeCoMe with skewed data where mean and median differ."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=2.0, peak=3.0, upper_bound=4.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=4.0, upper_bound=5.0),
            ),
            ExpertOpinion(
                expert_id="E4",
                opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=11.0, upper_bound=12.0),
            ),
            ExpertOpinion(
                expert_id="E5",
                opinion=FuzzyTriangleNumber(lower_bound=11.0, peak=12.0, upper_bound=13.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_compromise(opinions)

        # Mean: (1+2+3+10+11)/5=5.4, (2+3+4+11+12)/5=6.4, (3+4+5+12+13)/5=7.4
        assert result.arithmetic_mean.lower_bound == 5.4
        assert result.arithmetic_mean.peak == 6.4
        assert result.arithmetic_mean.upper_bound == 7.4

        # Median (odd, middle E3): (3, 4, 5)
        assert result.median.lower_bound == 3.0
        assert result.median.peak == 4.0
        assert result.median.upper_bound == 5.0

        # Compromise: ((5.4+3)/2, (6.4+4)/2, (7.4+5)/2) = (4.2, 5.2, 6.2)
        assert result.best_compromise.lower_bound == 4.2
        assert result.best_compromise.peak == 5.2
        assert result.best_compromise.upper_bound == 6.2

        # Error: |centroid(mean) - centroid(median)| / 2
        # Mean centroid: (5.4 + 6.4 + 7.4) / 3 = 6.4
        # Median centroid: (3 + 4 + 5) / 3 = 4.0
        # Max error: |6.4 - 4.0| / 2 = 1.2
        assert abs(result.max_error - 1.2) < 1e-10

    def test_compromise_with_single_expert(self):
        """Test BeCoMe with single expert (edge case)."""
        opinion = ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        )

        calculator = BeCoMeCalculator()
        result = calculator.calculate_compromise([opinion])

        assert result.num_experts == 1
        assert result.is_even is False

        # Single expert: mean = median = opinion
        # So compromise = opinion, error = 0
        assert result.arithmetic_mean.lower_bound == 5.0
        assert result.arithmetic_mean.peak == 10.0
        assert result.arithmetic_mean.upper_bound == 15.0

        assert result.median.lower_bound == 5.0
        assert result.median.peak == 10.0
        assert result.median.upper_bound == 15.0

        assert result.best_compromise.lower_bound == 5.0
        assert result.best_compromise.peak == 10.0
        assert result.best_compromise.upper_bound == 15.0

        # Max error is now a scalar (float) - distance between centroids
        assert result.max_error == 0.0

    def test_compromise_empty_list_raises_error(self):
        """Test that empty opinions list raises ValueError."""
        calculator = BeCoMeCalculator()

        with pytest.raises(ValueError) as exc_info:
            calculator.calculate_compromise([])

        assert "empty" in str(exc_info.value).lower()

    def test_compromise_result_structure(self):
        """Test that result contains all required fields."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=12.0, upper_bound=17.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_compromise(opinions)

        # Check all fields are present and have correct types
        assert hasattr(result, "best_compromise")
        assert hasattr(result, "arithmetic_mean")
        assert hasattr(result, "median")
        assert hasattr(result, "max_error")
        assert hasattr(result, "num_experts")
        assert hasattr(result, "is_even")

        assert isinstance(result.num_experts, int)
        assert isinstance(result.is_even, bool)

    def test_compromise_preserves_fuzzy_constraint(self):
        """Test that all fuzzy numbers in result maintain constraint."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=2.0, peak=5.0, upper_bound=8.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=4.0, peak=7.0, upper_bound=10.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=9.0, upper_bound=12.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_compromise(opinions)

        # Check all fuzzy numbers maintain lower <= peak <= upper
        assert result.arithmetic_mean.lower_bound <= result.arithmetic_mean.peak
        assert result.arithmetic_mean.peak <= result.arithmetic_mean.upper_bound

        assert result.median.lower_bound <= result.median.peak
        assert result.median.peak <= result.median.upper_bound

        assert result.best_compromise.lower_bound <= result.best_compromise.peak
        assert result.best_compromise.peak <= result.best_compromise.upper_bound

        # Max error is now a scalar (float), so just check it's non-negative
        assert result.max_error >= 0.0

    def test_compromise_max_error_calculation(self):
        """Test that max_error is calculated correctly."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=0.0, peak=5.0, upper_bound=10.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_compromise(opinions)

        # Mean: (0+10)/2=5, (5+15)/2=10, (10+20)/2=15 → (5, 10, 15)
        # Median (even): ((0+10)/2, (5+15)/2, (10+20)/2) = (5, 10, 15)
        # Mean centroid: (5 + 10 + 15) / 3 = 10
        # Median centroid: (5 + 10 + 15) / 3 = 10
        # Error: |10 - 10| / 2 = 0

        # Verify error is half the distance between centroids
        mean_centroid = result.arithmetic_mean.get_centroid()
        median_centroid = result.median.get_centroid()
        expected_error = abs(mean_centroid - median_centroid) / 2

        assert abs(result.max_error - expected_error) < 1e-10
