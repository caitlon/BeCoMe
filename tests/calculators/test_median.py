"""
Unit tests for BeCoMeCalculator.calculate_median() method.
"""

import pytest

from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


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

