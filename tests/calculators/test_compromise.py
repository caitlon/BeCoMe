"""
Unit tests for BeCoMeCalculator.calculate_compromise() method.

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
def five_experts_skewed_opinions():
    """
    Provide 5 experts with skewed distribution.

    Creates scenario where mean and median differ significantly.
    """
    return [
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


@pytest.fixture
def two_experts_for_error_calculation():
    """Provide two experts for testing error calculation."""
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=0.0, peak=5.0, upper_bound=10.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0),
        ),
    ]


class TestBeCoMeCalculatorCompromise:
    """
    Test cases for full BeCoMe compromise calculation.

    Uses class-scoped calculator fixture for efficiency.
    """

    def test_compromise_with_three_experts_odd(self, calculator, three_experts_opinions):
        """
        Test full BeCoMe calculation with 3 experts (odd).

        Edge case where mean equals median (max_error = 0).

        GIVEN: Three expert opinions with sequential values
        WHEN: Calculating compromise
        THEN: Mean equals median, resulting in zero error
        """
        # GIVEN: Fixtures provide calculator and three expert opinions
        # (E1: 3-6-9, E2: 6-9-12, E3: 9-12-15)

        # WHEN: Calculate compromise
        result = calculator.calculate_compromise(three_experts_opinions)

        # THEN: Result contains all components
        assert result is not None
        assert result.num_experts == 3
        assert result.is_even is False

        # THEN: Mean is calculated correctly
        # Mean: (3+6+9)/3=6, (6+9+12)/3=9, (9+12+15)/3=12 → (6, 9, 12)
        assert result.arithmetic_mean.lower_bound == 6.0
        assert result.arithmetic_mean.peak == 9.0
        assert result.arithmetic_mean.upper_bound == 12.0

        # THEN: Median equals mean (edge case for sequential data)
        # Median (odd, middle): (6, 9, 12)
        assert result.median.lower_bound == 6.0
        assert result.median.peak == 9.0
        assert result.median.upper_bound == 12.0

        # THEN: Compromise equals both mean and median
        # Compromise: ((6+6)/2, (9+9)/2, (12+12)/2) = (6, 9, 12)
        assert result.best_compromise.lower_bound == 6.0
        assert result.best_compromise.peak == 9.0
        assert result.best_compromise.upper_bound == 12.0

        # THEN: Max error is 0 when mean == median
        # Error: |centroid(6,9,12) - centroid(6,9,12)| / 2 = 0
        assert result.max_error == 0.0

    def test_compromise_with_four_experts_even(self, calculator, four_experts_even_opinions):
        """
        Test full BeCoMe calculation with 4 experts (even).

        Edge case where mean equals median (max_error = 0).

        GIVEN: Four expert opinions with sequential values
        WHEN: Calculating compromise
        THEN: Mean equals median, resulting in zero error
        """
        # GIVEN: Fixtures provide calculator and four expert opinions
        # (E1: 1-2-3, E2: 4-5-6, E3: 7-8-9, E4: 10-11-12)

        # WHEN: Calculate compromise
        result = calculator.calculate_compromise(four_experts_even_opinions)

        # THEN: Result metadata is correct
        assert result.num_experts == 4
        assert result.is_even is True

        # THEN: Best compromise is correct (mean equals median for sequential data)
        # Mean: (1+4+7+10)/4=5.5, (2+5+8+11)/4=6.5, (3+6+9+12)/4=7.5
        # Median (even): avg of E2 and E3 → (5.5, 6.5, 7.5)
        # Same values, so compromise = (5.5, 6.5, 7.5), error = 0
        assert result.best_compromise.lower_bound == 5.5
        assert result.best_compromise.peak == 6.5
        assert result.best_compromise.upper_bound == 7.5

        # THEN: Max error is 0 when mean == median (edge case)
        assert result.max_error == 0.0

    def test_compromise_with_skewed_data(self, calculator, five_experts_skewed_opinions):
        """
        Test BeCoMe with skewed data where mean and median differ.

        This is the main scenario - testing real compromise calculation.

        GIVEN: Five expert opinions with skewed distribution
        WHEN: Calculating compromise
        THEN: Mean and median differ, compromise is their average, error > 0
        """
        # GIVEN: Fixture provides skewed opinions
        # (E1: 1-2-3, E2: 2-3-4, E3: 3-4-5, E4: 10-11-12, E5: 11-12-13)

        # WHEN: Calculate compromise
        result = calculator.calculate_compromise(five_experts_skewed_opinions)

        # THEN: Mean is calculated correctly (affected by outliers)
        # Mean: (1+2+3+10+11)/5=5.4, (2+3+4+11+12)/5=6.4, (3+4+5+12+13)/5=7.4
        assert result.arithmetic_mean.lower_bound == 5.4
        assert result.arithmetic_mean.peak == 6.4
        assert result.arithmetic_mean.upper_bound == 7.4

        # THEN: Median is calculated correctly (robust to outliers)
        # Median (odd, middle E3): (3, 4, 5)
        assert result.median.lower_bound == 3.0
        assert result.median.peak == 4.0
        assert result.median.upper_bound == 5.0

        # THEN: Compromise is average of mean and median
        # Compromise: ((5.4+3)/2, (6.4+4)/2, (7.4+5)/2) = (4.2, 5.2, 6.2)
        assert result.best_compromise.lower_bound == 4.2
        assert result.best_compromise.peak == 5.2
        assert result.best_compromise.upper_bound == 6.2

        # THEN: Max error represents distance between mean and median
        # Error: |centroid(mean) - centroid(median)| / 2
        # Mean centroid: (5.4 + 6.4 + 7.4) / 3 = 6.4
        # Median centroid: (3 + 4 + 5) / 3 = 4.0
        # Max error: |6.4 - 4.0| / 2 = 1.2
        assert abs(result.max_error - 1.2) < 1e-10

    def test_compromise_with_single_expert(self, calculator, single_expert_opinion):
        """
        Test BeCoMe with single expert (edge case).

        GIVEN: One expert opinion
        WHEN: Calculating compromise
        THEN: Mean, median, and compromise all equal the single opinion
        """
        # GIVEN: Fixture provides single expert opinion (5-10-15)

        # WHEN: Calculate compromise
        result = calculator.calculate_compromise(single_expert_opinion)

        # THEN: Result metadata is correct
        assert result.num_experts == 1
        assert result.is_even is False

        # THEN: All aggregations equal the single opinion
        # Single expert: mean = median = opinion
        assert result.arithmetic_mean.lower_bound == 5.0
        assert result.arithmetic_mean.peak == 10.0
        assert result.arithmetic_mean.upper_bound == 15.0

        assert result.median.lower_bound == 5.0
        assert result.median.peak == 10.0
        assert result.median.upper_bound == 15.0

        assert result.best_compromise.lower_bound == 5.0
        assert result.best_compromise.peak == 10.0
        assert result.best_compromise.upper_bound == 15.0

        # THEN: Max error is 0 (no disagreement)
        assert result.max_error == 0.0

    def test_compromise_empty_list_raises_error(self, calculator):
        """
        Test that empty opinions list raises EmptyOpinionsError.

        GIVEN: Empty list of opinions
        WHEN: Attempting to calculate compromise
        THEN: EmptyOpinionsError is raised
        """
        # GIVEN: Empty opinions list

        # WHEN/THEN: Attempting calculation raises EmptyOpinionsError
        with pytest.raises(EmptyOpinionsError) as exc_info:
            calculator.calculate_compromise([])

        # THEN: Error message mentions "empty"
        assert "empty" in str(exc_info.value).lower()

    def test_compromise_max_error_calculation(self, calculator, two_experts_for_error_calculation):
        """
        Test that max_error is calculated correctly.

        GIVEN: Two experts with opinions at different ranges
        WHEN: Calculating compromise
        THEN: Max error equals half the distance between mean and median centroids
        """
        # GIVEN: Fixture provides two experts with different ranges
        # (E1: 0-5-10, E2: 10-15-20)

        # WHEN: Calculate compromise
        result = calculator.calculate_compromise(two_experts_for_error_calculation)

        # THEN: Mean and median are calculated correctly
        # Mean: (0+10)/2=5, (5+15)/2=10, (10+20)/2=15 → (5, 10, 15)
        # Median (even): ((0+10)/2, (5+15)/2, (10+20)/2) = (5, 10, 15)
        # Mean centroid: (5 + 10 + 15) / 3 = 10
        # Median centroid: (5 + 10 + 15) / 3 = 10
        # Error: |10 - 10| / 2 = 0

        # THEN: Max error equals half the distance between centroids
        mean_centroid = result.arithmetic_mean.centroid
        median_centroid = result.median.centroid
        expected_error = abs(mean_centroid - median_centroid) / 2

        assert abs(result.max_error - expected_error) < 1e-10
