"""
Unit tests for BeCoMeCalculator.calculate_arithmetic_mean() method.

Following Lott's "Python Object-Oriented Programming" (Chapter 13):
- Tests structured as GIVEN-WHEN-THEN
- Fixtures provide test data (Dependency Injection)
- Each test validates a single behavior
"""

import pytest

from src.exceptions import EmptyOpinionsError
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

# Local fixtures (used only in this file)


@pytest.fixture
def two_experts_decimal_opinions():
    """Provide opinions from 2 experts with decimal values."""
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
    """Provide opinions to test component independence."""
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
    """
    Test cases for arithmetic mean calculation.

    Uses class-scoped calculator fixture for efficiency.
    """

    def test_arithmetic_mean_with_three_experts(self, calculator, three_experts_opinions):
        """
        Test arithmetic mean calculation with 3 experts.

        GIVEN: Three expert opinions with sequential values
        WHEN: Calculating arithmetic mean
        THEN: Result is average of all components
        """
        # GIVEN: Fixtures provide calculator and three expert opinions
        # (E1: 3-6-9, E2: 6-9-12, E3: 9-12-15)

        # WHEN: Calculate arithmetic mean
        result = calculator.calculate_arithmetic_mean(three_experts_opinions)

        # THEN: Result is component-wise average
        # Lower: (3 + 6 + 9) / 3 = 6.0
        # Peak: (6 + 9 + 12) / 3 = 9.0
        # Upper: (9 + 12 + 15) / 3 = 12.0
        assert result.lower_bound == 6.0
        assert result.peak == 9.0
        assert result.upper_bound == 12.0

    def test_arithmetic_mean_with_single_expert(self, calculator, single_expert_opinion):
        """
        Test arithmetic mean with single expert returns same values.

        GIVEN: One expert opinion
        WHEN: Calculating arithmetic mean
        THEN: Result equals the single expert's opinion
        """
        # GIVEN: Fixture provides single expert opinion (5-10-15)

        # WHEN: Calculate arithmetic mean
        result = calculator.calculate_arithmetic_mean(single_expert_opinion)

        # THEN: Mean equals the single expert's values
        assert result.lower_bound == 5.0
        assert result.peak == 10.0
        assert result.upper_bound == 15.0

    def test_arithmetic_mean_with_decimal_values(self, calculator, two_experts_decimal_opinions):
        """
        Test arithmetic mean with decimal values.

        GIVEN: Two expert opinions with decimal values
        WHEN: Calculating arithmetic mean
        THEN: Result correctly averages decimal values
        """
        # GIVEN: Fixture provides two opinions with decimals
        # (E1: 2.5-5.5-8.5, E2: 3.5-6.5-9.5)

        # WHEN: Calculate arithmetic mean
        result = calculator.calculate_arithmetic_mean(two_experts_decimal_opinions)

        # THEN: Result is average with proper decimal handling
        # Lower: (2.5 + 3.5) / 2 = 3.0
        # Peak: (5.5 + 6.5) / 2 = 6.0
        # Upper: (8.5 + 9.5) / 2 = 9.0
        assert result.lower_bound == 3.0
        assert result.peak == 6.0
        assert result.upper_bound == 9.0

    def test_arithmetic_mean_empty_list_raises_error(self, calculator):
        """
        Test that empty opinions list raises EmptyOpinionsError.

        GIVEN: Empty list of opinions
        WHEN: Attempting to calculate arithmetic mean
        THEN: EmptyOpinionsError is raised with appropriate message
        """
        # GIVEN: Empty opinions list

        # WHEN/THEN: Attempting calculation raises EmptyOpinionsError
        with pytest.raises(EmptyOpinionsError) as exc_info:
            calculator.calculate_arithmetic_mean([])

        # THEN: Error message mentions "empty"
        assert "empty" in str(exc_info.value).lower()

    def test_arithmetic_mean_component_independence(
        self, calculator, two_experts_independent_components
    ):
        """
        Test that each component is calculated independently.

        GIVEN: Two opinions with different component values
        WHEN: Calculating arithmetic mean
        THEN: Each component is averaged independently
        """
        # GIVEN: Fixture provides opinions with independent components
        # (E1: 10-10-10, E2: 20-30-40)

        # WHEN: Calculate arithmetic mean
        result = calculator.calculate_arithmetic_mean(two_experts_independent_components)

        # THEN: Each component is averaged independently
        assert result.lower_bound == 15.0  # (10 + 20) / 2
        assert result.peak == 20.0  # (10 + 30) / 2
        assert result.upper_bound == 25.0  # (10 + 40) / 2
