"""
Unit tests for BeCoMeCalculator.calculate_median() method.

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
def two_experts_for_median():
    """Provide opinions from 2 experts for median calculation."""
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=9.0, upper_bound=12.0),
        ),
    ]


@pytest.fixture
def five_experts_for_median():
    """Provide opinions from 5 experts for median calculation."""
    return [
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


@pytest.fixture
def six_experts_for_median():
    """Provide opinions from 6 experts for median calculation."""
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=2.0, peak=3.0, upper_bound=4.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=4.0, peak=5.0, upper_bound=6.0),
        ),
        ExpertOpinion(
            expert_id="E3",
            opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=7.0, upper_bound=8.0),
        ),
        ExpertOpinion(
            expert_id="E4",
            opinion=FuzzyTriangleNumber(lower_bound=8.0, peak=9.0, upper_bound=10.0),
        ),
        ExpertOpinion(
            expert_id="E5",
            opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=11.0, upper_bound=12.0),
        ),
        ExpertOpinion(
            expert_id="E6",
            opinion=FuzzyTriangleNumber(lower_bound=12.0, peak=13.0, upper_bound=14.0),
        ),
    ]


@pytest.fixture
def seven_experts_for_median():
    """Provide opinions from 7 experts for median calculation."""
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
            opinion=FuzzyTriangleNumber(lower_bound=4.0, peak=5.0, upper_bound=6.0),
        ),
        ExpertOpinion(
            expert_id="E5",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=6.0, upper_bound=7.0),
        ),
        ExpertOpinion(
            expert_id="E6",
            opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=7.0, upper_bound=8.0),
        ),
        ExpertOpinion(
            expert_id="E7",
            opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=8.0, upper_bound=9.0),
        ),
    ]


@pytest.fixture
def three_experts_unsorted():
    """Provide unsorted opinions to test sorting by centroid."""
    return [
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


class TestBeCoMeCalculatorMedian:
    """
    Test cases for median calculation.

    Uses class-scoped calculator fixture for efficiency.
    """

    def test_median_with_three_experts_odd(self, calculator, three_experts_opinions):
        """
        Test median calculation with 3 experts (odd).

        GIVEN: Three expert opinions with sequential values
        WHEN: Calculating median
        THEN: Median is the middle element after sorting by centroid
        """
        # GIVEN: Fixtures provide calculator and three expert opinions
        # (E1: 3-6-9, E2: 6-9-12, E3: 9-12-15)

        # WHEN: Calculate median
        result = calculator.calculate_median(three_experts_opinions)

        # THEN: Result is the middle element (E2) after sorting by centroid
        # Sorted by centroid: E1(6.0), E2(9.0), E3(12.0)
        # Middle element at index 1: E2 (6, 9, 12)
        assert result.lower_bound == 6.0
        assert result.peak == 9.0
        assert result.upper_bound == 12.0

    def test_median_with_five_experts_odd(self, calculator, five_experts_for_median):
        """
        Test median calculation with 5 experts (odd).

        GIVEN: Five expert opinions with sequential values
        WHEN: Calculating median
        THEN: Median is the middle element at index 2
        """
        # GIVEN: Fixture provides five expert opinions
        # (E1: 1-2-3, E2: 4-5-6, E3: 7-8-9, E4: 10-11-12, E5: 13-14-15)

        # WHEN: Calculate median
        result = calculator.calculate_median(five_experts_for_median)

        # THEN: Result is the middle element (E3) after sorting
        # Middle element at index 2: E3 (7, 8, 9)
        assert result.lower_bound == 7.0
        assert result.peak == 8.0
        assert result.upper_bound == 9.0

    def test_median_with_seven_experts_odd(self, calculator, seven_experts_for_median):
        """
        Test median calculation with 7 experts (odd).

        GIVEN: Seven expert opinions with sequential values
        WHEN: Calculating median
        THEN: Median is the middle element at index 3
        """
        # GIVEN: Fixture provides seven expert opinions
        # (E1: 1-2-3, E2: 2-3-4, E3: 3-4-5, E4: 4-5-6, E5: 5-6-7, E6: 6-7-8, E7: 7-8-9)

        # WHEN: Calculate median
        result = calculator.calculate_median(seven_experts_for_median)

        # THEN: Result is the middle element (E4) after sorting
        # Middle element at index 3: E4 (4, 5, 6)
        assert result.lower_bound == 4.0
        assert result.peak == 5.0
        assert result.upper_bound == 6.0

    def test_median_with_two_experts_even(self, calculator, two_experts_for_median):
        """
        Test median calculation with 2 experts (even).

        GIVEN: Two expert opinions with sequential values
        WHEN: Calculating median
        THEN: Median is average of two elements
        """
        # GIVEN: Fixture provides two expert opinions
        # (E1: 3-6-9, E2: 6-9-12)

        # WHEN: Calculate median
        result = calculator.calculate_median(two_experts_for_median)

        # THEN: Result is average of the two elements
        # Average: ((3+6)/2, (6+9)/2, (9+12)/2) = (4.5, 7.5, 10.5)
        assert result.lower_bound == 4.5
        assert result.peak == 7.5
        assert result.upper_bound == 10.5

    def test_median_with_four_experts_even(self, calculator, four_experts_even_opinions):
        """
        Test median calculation with 4 experts (even).

        GIVEN: Four expert opinions with sequential values
        WHEN: Calculating median
        THEN: Median is average of middle two elements
        """
        # GIVEN: Fixture provides four expert opinions
        # (E1: 1-2-3, E2: 4-5-6, E3: 7-8-9, E4: 10-11-12)

        # WHEN: Calculate median
        result = calculator.calculate_median(four_experts_even_opinions)

        # THEN: Result is average of middle two elements (E2 and E3)
        # Average of indices 1 and 2: ((4+7)/2, (5+8)/2, (6+9)/2) = (5.5, 6.5, 7.5)
        assert result.lower_bound == 5.5
        assert result.peak == 6.5
        assert result.upper_bound == 7.5

    def test_median_with_six_experts_even(self, calculator, six_experts_for_median):
        """
        Test median calculation with 6 experts (even).

        GIVEN: Six expert opinions with sequential values
        WHEN: Calculating median
        THEN: Median is average of middle two elements
        """
        # GIVEN: Fixture provides six expert opinions
        # (E1: 2-3-4, E2: 4-5-6, E3: 6-7-8, E4: 8-9-10, E5: 10-11-12, E6: 12-13-14)

        # WHEN: Calculate median
        result = calculator.calculate_median(six_experts_for_median)

        # THEN: Result is average of middle two elements (E3 and E4)
        # Average of indices 2 and 3: ((6+8)/2, (7+9)/2, (8+10)/2) = (7.0, 8.0, 9.0)
        assert result.lower_bound == 7.0
        assert result.peak == 8.0
        assert result.upper_bound == 9.0

    def test_median_with_single_expert(self, calculator, single_expert_opinion):
        """
        Test median with single expert returns same values.

        GIVEN: One expert opinion
        WHEN: Calculating median
        THEN: Median equals the single expert's opinion
        """
        # GIVEN: Fixture provides single expert opinion (5-10-15)

        # WHEN: Calculate median
        result = calculator.calculate_median(single_expert_opinion)

        # THEN: Median equals the single expert's values
        # Single expert: median = opinion
        assert result.lower_bound == 5.0
        assert result.peak == 10.0
        assert result.upper_bound == 15.0

    def test_median_empty_list_raises_error(self, calculator):
        """
        Test that empty opinions list raises EmptyOpinionsError.

        GIVEN: Empty list of opinions
        WHEN: Attempting to calculate median
        THEN: EmptyOpinionsError is raised with appropriate message
        """
        # GIVEN: Empty opinions list

        # WHEN/THEN: Attempting calculation raises EmptyOpinionsError
        with pytest.raises(EmptyOpinionsError) as exc_info:
            calculator.calculate_median([])

        # THEN: Error message mentions "empty"
        assert "empty" in str(exc_info.value).lower()

    def test_median_sorts_by_centroid(self, calculator, three_experts_unsorted):
        """
        Test that median correctly sorts opinions by centroid before calculation.

        GIVEN: Three unsorted opinions (High, Low, Mid)
        WHEN: Calculating median
        THEN: Median is middle element after sorting by centroid
        """
        # GIVEN: Fixture provides unsorted opinions
        # (High: 15-18-21 [centroid=18.0], Low: 3-6-9 [centroid=6.0], Mid: 9-12-15 [centroid=12.0])

        # WHEN: Calculate median
        result = calculator.calculate_median(three_experts_unsorted)

        # THEN: Result is middle element after sorting by centroid
        # Sorted by centroid: Low(6.0), Mid(12.0), High(18.0)
        # Middle element: Mid (9, 12, 15)
        assert result.lower_bound == 9.0
        assert result.peak == 12.0
        assert result.upper_bound == 15.0
