"""Unit tests for median calculation strategies."""

import pytest

from src.calculators.median_strategies import (
    EvenMedianStrategy,
    MedianCalculationStrategy,
    OddMedianStrategy,
)
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture
def one_expert_for_odd_strategy():
    """Provide single expert for odd median strategy test.

    :return: List of 1 ExpertOpinion instance
    """
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        ),
    ]


@pytest.fixture
def three_experts_for_odd_strategy():
    """Provide three experts for odd median strategy test.

    :return: List of 3 ExpertOpinion instances
    """
    return [
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


@pytest.fixture
def five_experts_for_odd_strategy():
    """Provide five experts for odd median strategy test.

    :return: List of 5 ExpertOpinion instances
    """
    return [
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


@pytest.fixture
def two_experts_for_even_strategy():
    """Provide two experts for even median strategy test.

    :return: List of 2 ExpertOpinion instances
    """
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
        ),
    ]


@pytest.fixture
def four_experts_for_even_strategy():
    """Provide four experts for even median strategy test.

    :return: List of 4 ExpertOpinion instances
    """
    return [
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


@pytest.fixture
def six_experts_for_even_strategy():
    """Provide six experts for even median strategy test.

    :return: List of 6 ExpertOpinion instances
    """
    return [
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


class TestMedianCalculationStrategyABC:
    """Test the abstract base class contract for median strategies."""

    def test_cannot_instantiate_abstract_base_class(self):
        """Test that MedianCalculationStrategy cannot be instantiated directly."""
        # WHEN / THEN
        with pytest.raises(TypeError):
            MedianCalculationStrategy()  # type: ignore

    def test_strategies_implement_abc_interface(self):
        """Test that both strategies implement ABC interface."""
        # WHEN / THEN
        assert issubclass(OddMedianStrategy, MedianCalculationStrategy)
        assert issubclass(EvenMedianStrategy, MedianCalculationStrategy)

        odd_strategy: MedianCalculationStrategy = OddMedianStrategy()
        even_strategy: MedianCalculationStrategy = EvenMedianStrategy()

        assert isinstance(odd_strategy, MedianCalculationStrategy)
        assert isinstance(even_strategy, MedianCalculationStrategy)


class TestOddMedianStrategy:
    """Test cases for OddMedianStrategy (odd number of experts)."""

    def test_odd_strategy_with_single_expert(self, one_expert_for_odd_strategy):
        """Test odd median strategy with single expert returns unchanged opinion."""
        # GIVEN
        median_centroid = 10.0

        # WHEN
        strategy = OddMedianStrategy()
        result = strategy.calculate(one_expert_for_odd_strategy, median_centroid)

        # THEN
        assert result.lower_bound == 5.0
        assert result.peak == 10.0
        assert result.upper_bound == 15.0

    def test_odd_strategy_with_three_experts(self, three_experts_for_odd_strategy):
        """Test odd median strategy with three experts returns middle element."""
        # GIVEN
        median_centroid = 9.0

        # WHEN
        strategy = OddMedianStrategy()
        result = strategy.calculate(three_experts_for_odd_strategy, median_centroid)

        # THEN
        assert result.lower_bound == 6.0
        assert result.peak == 9.0
        assert result.upper_bound == 12.0

    def test_odd_strategy_with_five_experts(self, five_experts_for_odd_strategy):
        """Test odd median strategy with five experts returns middle element."""
        # GIVEN
        median_centroid = 8.0

        # WHEN
        strategy = OddMedianStrategy()
        result = strategy.calculate(five_experts_for_odd_strategy, median_centroid)

        # THEN
        assert result.lower_bound == 5.0
        assert result.peak == 8.0
        assert result.upper_bound == 11.0


class TestEvenMedianStrategy:
    """Test cases for EvenMedianStrategy (even number of experts)."""

    def test_even_strategy_with_two_experts(self, two_experts_for_even_strategy):
        """Test even median strategy with two experts returns average."""
        # GIVEN
        median_centroid = 9.0

        # WHEN
        strategy = EvenMedianStrategy()
        result = strategy.calculate(two_experts_for_even_strategy, median_centroid)

        # THEN
        assert result.lower_bound == 6.0
        assert result.peak == 9.0
        assert result.upper_bound == 12.0

    def test_even_strategy_with_four_experts(self, four_experts_for_even_strategy):
        """Test even median strategy with four experts returns average of middle two."""
        # GIVEN
        median_centroid = 8.5

        # WHEN
        strategy = EvenMedianStrategy()
        result = strategy.calculate(four_experts_for_even_strategy, median_centroid)

        # THEN
        assert result.lower_bound == 5.0
        assert result.peak == 8.5
        assert result.upper_bound == 12.0

    def test_even_strategy_with_six_experts(self, six_experts_for_even_strategy):
        """Test even median strategy with six experts returns average of middle two."""
        # GIVEN
        median_centroid = 9.5

        # WHEN
        strategy = EvenMedianStrategy()
        result = strategy.calculate(six_experts_for_even_strategy, median_centroid)

        # THEN
        assert result.lower_bound == 6.0
        assert result.peak == 9.5
        assert result.upper_bound == 13.0
