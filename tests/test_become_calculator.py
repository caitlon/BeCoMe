"""
Unit tests for BeCoMeCalculator class.
"""

import pytest
from src.models.fuzzy_number import FuzzyTriangleNumber
from src.models.expert_opinion import ExpertOpinion
from src.calculators.become_calculator import BeCoMeCalculator


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
                opinion=FuzzyTriangleNumber(
                    lower_bound=6.0, peak=9.0, upper_bound=12.0
                ),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(
                    lower_bound=9.0, peak=12.0, upper_bound=15.0
                ),
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
        identical_opinion = FuzzyTriangleNumber(
            lower_bound=7.0, peak=10.0, upper_bound=13.0
        )
        opinions = [
            ExpertOpinion(expert_id=f"E{i}", opinion=identical_opinion)
            for i in range(5)
        ]

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
                opinion=FuzzyTriangleNumber(
                    lower_bound=1.0, peak=5.0, upper_bound=10.0
                ),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(
                    lower_bound=2.0, peak=6.0, upper_bound=12.0
                ),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(
                    lower_bound=3.0, peak=7.0, upper_bound=14.0
                ),
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
                opinion=FuzzyTriangleNumber(
                    lower_bound=5.0, peak=8.0, upper_bound=11.0
                ),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(
                    lower_bound=6.0, peak=9.0, upper_bound=12.0
                ),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(
                    lower_bound=7.0, peak=10.0, upper_bound=13.0
                ),
            ),
            ExpertOpinion(
                expert_id="E4",
                opinion=FuzzyTriangleNumber(
                    lower_bound=8.0, peak=11.0, upper_bound=14.0
                ),
            ),
            ExpertOpinion(
                expert_id="E5",
                opinion=FuzzyTriangleNumber(
                    lower_bound=9.0, peak=12.0, upper_bound=15.0
                ),
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
                opinion=FuzzyTriangleNumber(
                    lower_bound=10.0, peak=10.0, upper_bound=10.0
                ),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(
                    lower_bound=20.0, peak=30.0, upper_bound=40.0
                ),
            ),
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_arithmetic_mean(opinions)

        # Each component averaged independently
        assert result.lower_bound == 15.0  # (10 + 20) / 2
        assert result.peak == 20.0  # (10 + 30) / 2
        assert result.upper_bound == 25.0  # (10 + 40) / 2
