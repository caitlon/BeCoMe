"""Unit tests for arithmetic mean calculation in BeCoMeCalculator."""

import pytest

from src.exceptions import EmptyOpinionsError
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture
def two_experts_decimal_opinions():
    """Provide opinions from two experts with decimal values.

    :return: List of 2 ExpertOpinion instances with decimal fuzzy numbers
    """
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=2.5, peak=5.5, upper_bound=8.5),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=3.5, peak=6.5, upper_bound=9.5),
        ),
    ]


@pytest.fixture
def two_experts_independent_components():
    """Provide opinions with independent component values for testing.

    :return: List of 2 ExpertOpinion instances with different component spreads
    """
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=10.0, upper_bound=10.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=20.0, peak=30.0, upper_bound=40.0),
        ),
    ]


class TestBeCoMeCalculatorArithmeticMean:
    """Test cases for arithmetic mean calculation."""

    def test_arithmetic_mean_with_three_experts(self, calculator, three_experts_opinions):
        """Test arithmetic mean with three sequential expert opinions."""
        # GIVEN
        expected_lower = 6.0
        expected_peak = 9.0
        expected_upper = 12.0

        # WHEN
        result = calculator.calculate_arithmetic_mean(three_experts_opinions)

        # THEN
        assert result.lower_bound == expected_lower
        assert result.peak == expected_peak
        assert result.upper_bound == expected_upper

    def test_arithmetic_mean_with_single_expert(self, calculator, single_expert_opinion):
        """Test arithmetic mean with single expert returns unchanged values."""
        # WHEN
        result = calculator.calculate_arithmetic_mean(single_expert_opinion)

        # THEN
        assert result.lower_bound == 5.0
        assert result.peak == 10.0
        assert result.upper_bound == 15.0

    def test_arithmetic_mean_with_decimal_values(self, calculator, two_experts_decimal_opinions):
        """Test arithmetic mean correctly handles decimal values."""
        # WHEN
        result = calculator.calculate_arithmetic_mean(two_experts_decimal_opinions)

        # THEN
        assert result.lower_bound == 3.0
        assert result.peak == 6.0
        assert result.upper_bound == 9.0

    def test_arithmetic_mean_empty_list_raises_error(self, calculator):
        """Test that empty opinions list raises EmptyOpinionsError."""
        # WHEN / THEN
        with pytest.raises(EmptyOpinionsError) as exc_info:
            calculator.calculate_arithmetic_mean([])

        assert "empty" in str(exc_info.value).lower()

    def test_arithmetic_mean_component_independence(
        self, calculator, two_experts_independent_components
    ):
        """Test that each fuzzy number component is calculated independently."""
        # WHEN
        result = calculator.calculate_arithmetic_mean(two_experts_independent_components)

        # THEN
        assert result.lower_bound == 15.0
        assert result.peak == 20.0
        assert result.upper_bound == 25.0
