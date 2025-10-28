"""
Unit tests for median calculation strategies.

This module tests the Strategy Pattern implementation for median calculation,
ensuring both OddMedianStrategy and EvenMedianStrategy correctly implement
the MedianCalculationStrategy ABC and produce correct results.
"""

import pytest

from src.calculators.median_strategies import (
    EvenMedianStrategy,
    MedianCalculationStrategy,
    OddMedianStrategy,
)
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


class TestMedianCalculationStrategyABC:
    """Test the abstract base class contract for median strategies."""

    def test_cannot_instantiate_abstract_base_class(self):
        """Test that MedianCalculationStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            MedianCalculationStrategy()  # type: ignore

    def test_abstract_method_is_defined(self):
        """Test that the abstract method 'calculate' is defined."""
        assert hasattr(MedianCalculationStrategy, "calculate")
        assert MedianCalculationStrategy.calculate.__isabstractmethod__

    def test_odd_strategy_inherits_from_abc(self):
        """Test that OddMedianStrategy inherits from MedianCalculationStrategy."""
        assert issubclass(OddMedianStrategy, MedianCalculationStrategy)

    def test_even_strategy_inherits_from_abc(self):
        """Test that EvenMedianStrategy inherits from MedianCalculationStrategy."""
        assert issubclass(EvenMedianStrategy, MedianCalculationStrategy)

    def test_strategies_can_be_used_polymorphically(self):
        """Test that strategies can be used through the abstract interface."""
        odd_strategy: MedianCalculationStrategy = OddMedianStrategy()
        even_strategy: MedianCalculationStrategy = EvenMedianStrategy()

        assert isinstance(odd_strategy, MedianCalculationStrategy)
        assert isinstance(even_strategy, MedianCalculationStrategy)


class TestOddMedianStrategy:
    """Test cases for OddMedianStrategy (odd number of experts)."""

    def test_odd_strategy_with_three_experts(self):
        """Test OddMedianStrategy with 3 experts - should return middle element."""
        sorted_opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
            ),  # centroid = 6.0
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=9.0, upper_bound=12.0),
            ),  # centroid = 9.0
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
            ),  # centroid = 12.0
        ]

        # Median centroid for [6.0, 9.0, 12.0] is 9.0
        median_centroid = 9.0

        strategy = OddMedianStrategy()
        result = strategy.calculate(sorted_opinions, median_centroid)

        # Should return E2 (middle element)
        assert result.lower_bound == 6.0
        assert result.peak == 9.0
        assert result.upper_bound == 12.0

    def test_odd_strategy_with_five_experts(self):
        """Test OddMedianStrategy with 5 experts."""
        sorted_opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0),
            ),  # centroid = 2.0
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=5.0, upper_bound=7.0),
            ),  # centroid = 5.0
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=8.0, upper_bound=11.0),
            ),  # centroid = 8.0
            ExpertOpinion(
                expert_id="E4",
                opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=11.0, upper_bound=15.0),
            ),  # centroid = 11.0
            ExpertOpinion(
                expert_id="E5",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=14.0, upper_bound=19.0),
            ),  # centroid = 14.0
        ]

        # Median centroid for [2, 5, 8, 11, 14] is 8.0
        median_centroid = 8.0

        strategy = OddMedianStrategy()
        result = strategy.calculate(sorted_opinions, median_centroid)

        # Should return E3 (middle element)
        assert result.lower_bound == 5.0
        assert result.peak == 8.0
        assert result.upper_bound == 11.0

    def test_odd_strategy_with_single_expert(self):
        """Test OddMedianStrategy with 1 expert."""
        sorted_opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            ),
        ]

        median_centroid = 10.0

        strategy = OddMedianStrategy()
        result = strategy.calculate(sorted_opinions, median_centroid)

        # Should return the only expert's opinion
        assert result.lower_bound == 5.0
        assert result.peak == 10.0
        assert result.upper_bound == 15.0


class TestEvenMedianStrategy:
    """Test cases for EvenMedianStrategy (even number of experts)."""

    def test_even_strategy_with_two_experts(self):
        """Test EvenMedianStrategy with 2 experts - should average both."""
        sorted_opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
            ),  # centroid = 6.0
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
            ),  # centroid = 12.0
        ]

        # Median centroid for [6.0, 12.0] is 9.0
        median_centroid = 9.0

        strategy = EvenMedianStrategy()
        result = strategy.calculate(sorted_opinions, median_centroid)

        # Should return average of E1 and E2
        # (3+9)/2=6, (6+12)/2=9, (9+15)/2=12
        assert result.lower_bound == 6.0
        assert result.peak == 9.0
        assert result.upper_bound == 12.0

    def test_even_strategy_with_four_experts(self):
        """Test EvenMedianStrategy with 4 experts."""
        sorted_opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=2.0, peak=4.0, upper_bound=6.0),
            ),  # centroid = 4.0
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=4.0, peak=7.0, upper_bound=10.0),
            ),  # centroid = 7.0
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=10.0, upper_bound=14.0),
            ),  # centroid = 10.0
            ExpertOpinion(
                expert_id="E4",
                opinion=FuzzyTriangleNumber(lower_bound=8.0, peak=13.0, upper_bound=18.0),
            ),  # centroid = 13.0
        ]

        # Median centroid for [4, 7, 10, 13] is 8.5
        median_centroid = 8.5

        strategy = EvenMedianStrategy()
        result = strategy.calculate(sorted_opinions, median_centroid)

        # Should return average of E2 and E3 (closest to 8.5)
        # (4+6)/2=5, (7+10)/2=8.5, (10+14)/2=12
        assert result.lower_bound == 5.0
        assert result.peak == 8.5
        assert result.upper_bound == 12.0

    def test_even_strategy_with_six_experts(self):
        """Test EvenMedianStrategy with 6 experts."""
        sorted_opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=5.0, upper_bound=7.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=8.0, upper_bound=11.0),
            ),
            ExpertOpinion(
                expert_id="E4",
                opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=11.0, upper_bound=15.0),
            ),
            ExpertOpinion(
                expert_id="E5",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=14.0, upper_bound=19.0),
            ),
            ExpertOpinion(
                expert_id="E6",
                opinion=FuzzyTriangleNumber(lower_bound=11.0, peak=17.0, upper_bound=23.0),
            ),
        ]

        # Median centroid for [2, 5, 8, 11, 14, 17] is 9.5
        median_centroid = 9.5

        strategy = EvenMedianStrategy()
        result = strategy.calculate(sorted_opinions, median_centroid)

        # Should return average of E3 and E4 (8.0 and 11.0 are closest to 9.5)
        # (5+7)/2=6, (8+11)/2=9.5, (11+15)/2=13
        assert result.lower_bound == 6.0
        assert result.peak == 9.5
        assert result.upper_bound == 13.0


class TestStrategyPatternIntegration:
    """Test integration of strategies with the overall system."""

    def test_strategies_return_fuzzy_triangle_number(self):
        """Test that both strategies return FuzzyTriangleNumber instances."""
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            ),
        ]

        odd_strategy = OddMedianStrategy()
        result = odd_strategy.calculate(opinions, 10.0)

        assert isinstance(result, FuzzyTriangleNumber)

    def test_strategies_preserve_fuzzy_number_constraint(self):
        """Test that strategy results preserve lower <= peak <= upper constraint."""
        sorted_opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=2.0, peak=5.0, upper_bound=8.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=4.0, peak=7.0, upper_bound=10.0),
            ),
        ]

        even_strategy = EvenMedianStrategy()
        result = even_strategy.calculate(sorted_opinions, 6.0)

        # Check constraint
        assert result.lower_bound <= result.peak <= result.upper_bound
