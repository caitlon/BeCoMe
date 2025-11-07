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

    def test_strategies_implement_abc_interface(self):
        """Test that both strategies properly inherit from and implement the ABC."""
        # Check inheritance
        assert issubclass(OddMedianStrategy, MedianCalculationStrategy)
        assert issubclass(EvenMedianStrategy, MedianCalculationStrategy)

        # Check polymorphic usage
        odd_strategy: MedianCalculationStrategy = OddMedianStrategy()
        even_strategy: MedianCalculationStrategy = EvenMedianStrategy()

        assert isinstance(odd_strategy, MedianCalculationStrategy)
        assert isinstance(even_strategy, MedianCalculationStrategy)


class TestOddMedianStrategy:
    """Test cases for OddMedianStrategy (odd number of experts)."""

    @pytest.mark.parametrize(
        "num_experts,expected_lower,expected_peak,expected_upper",
        [
            (1, 5.0, 10.0, 15.0),  # Single expert
            (3, 6.0, 9.0, 12.0),  # Middle element at index 1
            (5, 5.0, 8.0, 11.0),  # Middle element at index 2
        ],
    )
    def test_odd_strategy_returns_middle_element(
        self, num_experts, expected_lower, expected_peak, expected_upper
    ):
        """Test OddMedianStrategy returns the middle element from sorted opinions."""
        if num_experts == 1:
            sorted_opinions = [
                ExpertOpinion(
                    expert_id="E1",
                    opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
                ),
            ]
            median_centroid = 10.0
        elif num_experts == 3:
            sorted_opinions = [
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
            median_centroid = 9.0
        else:  # 5 experts
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
            ]
            median_centroid = 8.0

        strategy = OddMedianStrategy()
        result = strategy.calculate(sorted_opinions, median_centroid)

        assert result.lower_bound == expected_lower
        assert result.peak == expected_peak
        assert result.upper_bound == expected_upper


class TestEvenMedianStrategy:
    """Test cases for EvenMedianStrategy (even number of experts)."""

    @pytest.mark.parametrize(
        "num_experts,expected_lower,expected_peak,expected_upper",
        [
            (2, 6.0, 9.0, 12.0),  # Average of two elements
            (4, 5.0, 8.5, 12.0),  # Average of middle two
            (6, 6.0, 9.5, 13.0),  # Average of middle two
        ],
    )
    def test_even_strategy_averages_middle_elements(
        self, num_experts, expected_lower, expected_peak, expected_upper
    ):
        """Test EvenMedianStrategy averages the two middle elements from sorted opinions."""
        if num_experts == 2:
            sorted_opinions = [
                ExpertOpinion(
                    expert_id="E1",
                    opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
                ),
                ExpertOpinion(
                    expert_id="E2",
                    opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
                ),
            ]
            median_centroid = 9.0
        elif num_experts == 4:
            sorted_opinions = [
                ExpertOpinion(
                    expert_id="E1",
                    opinion=FuzzyTriangleNumber(lower_bound=2.0, peak=4.0, upper_bound=6.0),
                ),
                ExpertOpinion(
                    expert_id="E2",
                    opinion=FuzzyTriangleNumber(lower_bound=4.0, peak=7.0, upper_bound=10.0),
                ),
                ExpertOpinion(
                    expert_id="E3",
                    opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=10.0, upper_bound=14.0),
                ),
                ExpertOpinion(
                    expert_id="E4",
                    opinion=FuzzyTriangleNumber(lower_bound=8.0, peak=13.0, upper_bound=18.0),
                ),
            ]
            median_centroid = 8.5
        else:  # 6 experts
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
            median_centroid = 9.5

        strategy = EvenMedianStrategy()
        result = strategy.calculate(sorted_opinions, median_centroid)

        assert result.lower_bound == expected_lower
        assert result.peak == expected_peak
        assert result.upper_bound == expected_upper
