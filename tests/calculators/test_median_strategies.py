"""
Unit tests for median calculation strategies.

Following Lott's "Python Object-Oriented Programming" (Chapter 13):
- Tests structured as GIVEN-WHEN-THEN
- Fixtures provide test data (Dependency Injection)
- Each test validates a single behavior

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


class TestMedianCalculationStrategyABC:
    """Test the abstract base class contract for median strategies."""

    def test_cannot_instantiate_abstract_base_class(self):
        """
        Test that MedianCalculationStrategy cannot be instantiated directly.

        GIVEN: MedianCalculationStrategy ABC
        WHEN: Attempting to instantiate it directly
        THEN: TypeError is raised
        """
        # GIVEN/WHEN/THEN: Cannot instantiate abstract base class
        with pytest.raises(TypeError):
            MedianCalculationStrategy()  # type: ignore

    def test_strategies_implement_abc_interface(self):
        """
        Test that both strategies properly inherit from and implement the ABC.

        GIVEN: OddMedianStrategy and EvenMedianStrategy classes
        WHEN: Checking inheritance and polymorphic usage
        THEN: Both are subclasses and can be used polymorphically
        """
        # GIVEN: Strategy classes exist

        # WHEN: Checking inheritance
        # THEN: Both strategies are subclasses of the ABC
        assert issubclass(OddMedianStrategy, MedianCalculationStrategy)
        assert issubclass(EvenMedianStrategy, MedianCalculationStrategy)

        # WHEN: Creating instances polymorphically
        odd_strategy: MedianCalculationStrategy = OddMedianStrategy()
        even_strategy: MedianCalculationStrategy = EvenMedianStrategy()

        # THEN: Instances are of the correct type
        assert isinstance(odd_strategy, MedianCalculationStrategy)
        assert isinstance(even_strategy, MedianCalculationStrategy)


class TestOddMedianStrategy:
    """Test cases for OddMedianStrategy (odd number of experts)."""

    def test_odd_strategy_with_single_expert(self, one_expert_for_odd_strategy):
        """
        Test OddMedianStrategy with single expert.

        GIVEN: One expert opinion
        WHEN: Calculating median using OddMedianStrategy
        THEN: Median equals the single expert's opinion
        """
        # GIVEN: Fixture provides single expert opinion (5-10-15)
        sorted_opinions = one_expert_for_odd_strategy
        median_centroid = 10.0

        # WHEN: Calculate median using OddMedianStrategy
        strategy = OddMedianStrategy()
        result = strategy.calculate(sorted_opinions, median_centroid)

        # THEN: Median equals the single expert's values
        # Middle element at index 0: (5, 10, 15)
        assert result.lower_bound == 5.0
        assert result.peak == 10.0
        assert result.upper_bound == 15.0

    def test_odd_strategy_with_three_experts(self, three_experts_for_odd_strategy):
        """
        Test OddMedianStrategy with 3 experts.

        GIVEN: Three expert opinions (already sorted)
        WHEN: Calculating median using OddMedianStrategy
        THEN: Median is the middle element at index 1
        """
        # GIVEN: Fixture provides three sorted opinions
        # (E1: 3-6-9, E2: 6-9-12, E3: 9-12-15)
        sorted_opinions = three_experts_for_odd_strategy
        median_centroid = 9.0

        # WHEN: Calculate median using OddMedianStrategy
        strategy = OddMedianStrategy()
        result = strategy.calculate(sorted_opinions, median_centroid)

        # THEN: Median is the middle element (index 1)
        # Middle element: E2 (6, 9, 12)
        assert result.lower_bound == 6.0
        assert result.peak == 9.0
        assert result.upper_bound == 12.0

    def test_odd_strategy_with_five_experts(self, five_experts_for_odd_strategy):
        """
        Test OddMedianStrategy with 5 experts.

        GIVEN: Five expert opinions (already sorted)
        WHEN: Calculating median using OddMedianStrategy
        THEN: Median is the middle element at index 2
        """
        # GIVEN: Fixture provides five sorted opinions
        # (E1: 1-2-3, E2: 3-5-7, E3: 5-8-11, E4: 7-11-15, E5: 9-14-19)
        sorted_opinions = five_experts_for_odd_strategy
        median_centroid = 8.0

        # WHEN: Calculate median using OddMedianStrategy
        strategy = OddMedianStrategy()
        result = strategy.calculate(sorted_opinions, median_centroid)

        # THEN: Median is the middle element (index 2)
        # Middle element: E3 (5, 8, 11)
        assert result.lower_bound == 5.0
        assert result.peak == 8.0
        assert result.upper_bound == 11.0


class TestEvenMedianStrategy:
    """Test cases for EvenMedianStrategy (even number of experts)."""

    def test_even_strategy_with_two_experts(self, two_experts_for_even_strategy):
        """
        Test EvenMedianStrategy with 2 experts.

        GIVEN: Two expert opinions (already sorted)
        WHEN: Calculating median using EvenMedianStrategy
        THEN: Median is average of both elements
        """
        # GIVEN: Fixture provides two sorted opinions
        # (E1: 3-6-9, E2: 9-12-15)
        sorted_opinions = two_experts_for_even_strategy
        median_centroid = 9.0

        # WHEN: Calculate median using EvenMedianStrategy
        strategy = EvenMedianStrategy()
        result = strategy.calculate(sorted_opinions, median_centroid)

        # THEN: Median is average of the two elements
        # Average: ((3+9)/2, (6+12)/2, (9+15)/2) = (6, 9, 12)
        assert result.lower_bound == 6.0
        assert result.peak == 9.0
        assert result.upper_bound == 12.0

    def test_even_strategy_with_four_experts(self, four_experts_for_even_strategy):
        """
        Test EvenMedianStrategy with 4 experts.

        GIVEN: Four expert opinions (already sorted)
        WHEN: Calculating median using EvenMedianStrategy
        THEN: Median is average of middle two elements
        """
        # GIVEN: Fixture provides four sorted opinions
        # (E1: 2-4-6, E2: 4-7-10, E3: 6-10-14, E4: 8-13-18)
        sorted_opinions = four_experts_for_even_strategy
        median_centroid = 8.5

        # WHEN: Calculate median using EvenMedianStrategy
        strategy = EvenMedianStrategy()
        result = strategy.calculate(sorted_opinions, median_centroid)

        # THEN: Median is average of middle two elements (indices 1 and 2)
        # Average: ((4+6)/2, (7+10)/2, (10+14)/2) = (5, 8.5, 12)
        assert result.lower_bound == 5.0
        assert result.peak == 8.5
        assert result.upper_bound == 12.0

    def test_even_strategy_with_six_experts(self, six_experts_for_even_strategy):
        """
        Test EvenMedianStrategy with 6 experts.

        GIVEN: Six expert opinions (already sorted)
        WHEN: Calculating median using EvenMedianStrategy
        THEN: Median is average of middle two elements
        """
        # GIVEN: Fixture provides six sorted opinions
        # (E1: 1-2-3, E2: 3-5-7, E3: 5-8-11, E4: 7-11-15, E5: 9-14-19, E6: 11-17-23)
        sorted_opinions = six_experts_for_even_strategy
        median_centroid = 9.5

        # WHEN: Calculate median using EvenMedianStrategy
        strategy = EvenMedianStrategy()
        result = strategy.calculate(sorted_opinions, median_centroid)

        # THEN: Median is average of middle two elements (indices 2 and 3)
        # Average: ((5+7)/2, (8+11)/2, (11+15)/2) = (6, 9.5, 13)
        assert result.lower_bound == 6.0
        assert result.peak == 9.5
        assert result.upper_bound == 13.0
