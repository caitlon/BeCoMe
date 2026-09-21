"""Unit tests for median calculation in BeCoMeCalculator."""

from itertools import permutations

import pytest

from src.exceptions import EmptyOpinionsError
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture
def two_experts_for_median():
    """Provide two experts for median calculation.

    :return: List of 2 ExpertOpinion instances
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
    ]


@pytest.fixture
def five_experts_for_median():
    """Provide five experts for median calculation.

    :return: List of 5 ExpertOpinion instances
    """
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
    """Provide six experts for median calculation.

    :return: List of 6 ExpertOpinion instances
    """
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
    """Provide opinions from 7 experts for median calculation.

    :return: List of 7 ExpertOpinion instances
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
    """Provide unsorted opinions to test sorting by centroid.

    :return: List of 3 ExpertOpinion instances in unsorted order
    """
    return [
        ExpertOpinion(
            expert_id="High",
            opinion=FuzzyTriangleNumber(lower_bound=15.0, peak=18.0, upper_bound=21.0),
        ),
        ExpertOpinion(
            expert_id="Low",
            opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
        ),
        ExpertOpinion(
            expert_id="Mid",
            opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
        ),
    ]


class TestBeCoMeCalculatorMedian:
    """Test cases for median calculation."""

    def test_median_with_three_experts_odd(self, calculator, three_experts_opinions):
        """Test median calculation with 3 experts (odd)."""
        # WHEN
        result = calculator.calculate_median(three_experts_opinions)

        # THEN
        assert result.lower_bound == 6.0
        assert result.peak == 9.0
        assert result.upper_bound == 12.0

    def test_median_with_five_experts_odd(self, calculator, five_experts_for_median):
        """Test median calculation with 5 experts (odd)."""
        # WHEN
        result = calculator.calculate_median(five_experts_for_median)

        # THEN
        assert result.lower_bound == 7.0
        assert result.peak == 8.0
        assert result.upper_bound == 9.0

    def test_median_with_seven_experts_odd(self, calculator, seven_experts_for_median):
        """Test median calculation with 7 experts (odd)."""
        # WHEN
        result = calculator.calculate_median(seven_experts_for_median)

        # THEN
        assert result.lower_bound == 4.0
        assert result.peak == 5.0
        assert result.upper_bound == 6.0

    def test_median_with_two_experts_even(self, calculator, two_experts_for_median):
        """Test median calculation with 2 experts (even)."""
        # WHEN
        result = calculator.calculate_median(two_experts_for_median)

        # THEN
        assert result.lower_bound == 4.5
        assert result.peak == 7.5
        assert result.upper_bound == 10.5

    def test_median_with_four_experts_even(self, calculator, four_experts_even_opinions):
        """Test median calculation with 4 experts (even)."""
        # WHEN
        result = calculator.calculate_median(four_experts_even_opinions)

        # THEN
        assert result.lower_bound == 5.5
        assert result.peak == 6.5
        assert result.upper_bound == 7.5

    def test_median_with_six_experts_even(self, calculator, six_experts_for_median):
        """Test median calculation with 6 experts (even)."""
        # WHEN
        result = calculator.calculate_median(six_experts_for_median)

        # THEN
        assert result.lower_bound == 7.0
        assert result.peak == 8.0
        assert result.upper_bound == 9.0

    def test_median_with_single_expert(self, calculator, single_expert_opinion):
        """Test median with single expert returns same values."""
        # WHEN
        result = calculator.calculate_median(single_expert_opinion)

        # THEN
        assert result.lower_bound == 5.0
        assert result.peak == 10.0
        assert result.upper_bound == 15.0

    def test_median_empty_list_raises_error(self, calculator):
        """Test that empty opinions list raises EmptyOpinionsError."""
        # WHEN/THEN
        with pytest.raises(EmptyOpinionsError) as exc_info:
            calculator.calculate_median([])

        assert "empty" in str(exc_info.value).lower()

    def test_median_sorts_by_centroid(self, calculator, three_experts_unsorted):
        """Test that median correctly sorts opinions by centroid before calculation."""
        # WHEN
        result = calculator.calculate_median(three_experts_unsorted)

        # THEN
        assert result.lower_bound == 9.0
        assert result.peak == 12.0
        assert result.upper_bound == 15.0


class TestMedianOrderIndependence:
    """Tied centroids and duplicate opinions must not make the result order-dependent."""

    def test_odd_median_with_tied_centroids_is_input_order_independent(self, calculator):
        """Every input ordering yields the same median when centroids tie."""
        # GIVEN: X and Y share centroid 2.0 with different triangles; Z sits far away
        x = ExpertOpinion("X", FuzzyTriangleNumber(lower_bound=0.0, peak=3.0, upper_bound=3.0))
        y = ExpertOpinion("Y", FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0))
        z = ExpertOpinion("Z", FuzzyTriangleNumber(lower_bound=10.0, peak=10.0, upper_bound=10.0))

        # WHEN: the median is computed for every permutation of the input
        medians = {
            (m.lower_bound, m.peak, m.upper_bound)
            for perm in permutations([x, y, z])
            for m in [calculator.calculate_median(list(perm))]
        }

        # THEN: all orderings agree, and ties resolve canonically (by triangle bounds)
        assert medians == {(1.0, 2.0, 3.0)}

    def test_compromise_with_tied_centroids_is_input_order_independent(self, calculator):
        """The full compromise result is identical for every input ordering."""
        # GIVEN: two opinions tie on centroid with different triangles
        x = ExpertOpinion("X", FuzzyTriangleNumber(lower_bound=0.0, peak=3.0, upper_bound=3.0))
        y = ExpertOpinion("Y", FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0))
        z = ExpertOpinion("Z", FuzzyTriangleNumber(lower_bound=10.0, peak=10.0, upper_bound=10.0))

        # WHEN
        results = {
            (
                r.best_compromise.lower_bound,
                r.best_compromise.peak,
                r.best_compromise.upper_bound,
                r.max_error,
            )
            for perm in permutations([x, y, z])
            for r in [calculator.calculate_compromise(list(perm))]
        }

        # THEN
        assert len(results) == 1

    def test_even_median_with_identical_middle_duplicates(self, calculator):
        """Two identical middle opinions average to themselves, not to a neighbour."""
        # GIVEN: the two middle opinions are exact duplicates (same id, same triangle)
        opinions = [
            ExpertOpinion("L", FuzzyTriangleNumber(lower_bound=1.0, peak=1.0, upper_bound=1.0)),
            ExpertOpinion("M", FuzzyTriangleNumber(lower_bound=4.0, peak=5.0, upper_bound=6.0)),
            ExpertOpinion("M", FuzzyTriangleNumber(lower_bound=4.0, peak=5.0, upper_bound=6.0)),
            ExpertOpinion("H", FuzzyTriangleNumber(lower_bound=9.0, peak=9.0, upper_bound=9.0)),
        ]

        # WHEN
        result = calculator.calculate_median(opinions)

        # THEN: the median is exactly the duplicated middle triangle
        assert result.lower_bound == 4.0
        assert result.peak == 5.0
        assert result.upper_bound == 6.0


class TestMedianTiedCentroids:
    """Fixed-order checks that a centroid tie is resolved by the canonical sort.

    Complements TestMedianOrderIndependence: those tests prove the result does not
    change across permutations, these pin down what the tied result actually is,
    for both the even (average of two middles) and odd (single middle) case.
    """

    def test_two_experts_identical_centroids(self, calculator):
        """Two experts with identical centroids should average both opinions."""
        # GIVEN: both have centroid = 10.0
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=8.0, peak=10.0, upper_bound=12.0),
            ),
        ]

        # WHEN
        result = calculator.calculate_median(opinions)

        # THEN: average of (5,10,15) and (8,10,12) = (6.5, 10, 13.5)
        assert result.lower_bound == 6.5
        assert result.peak == 10.0
        assert result.upper_bound == 13.5

    def test_four_experts_middle_two_same_centroid(self, calculator):
        """Four experts where middle two have same centroid."""
        # GIVEN: E2 and E3 both have centroid = 10.0
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=8.0, peak=10.0, upper_bound=12.0),
            ),
            ExpertOpinion(
                expert_id="E4",
                opinion=FuzzyTriangleNumber(lower_bound=18.0, peak=19.0, upper_bound=20.0),
            ),
        ]

        # WHEN
        result = calculator.calculate_median(opinions)

        # THEN: both middle elements have centroid=10, averages E2 and E3
        assert result.lower_bound == 6.5
        assert result.peak == 10.0
        assert result.upper_bound == 13.5

    def test_all_centroids_identical(self, calculator):
        """All experts have identical centroids."""
        # GIVEN: all have centroid = 10.0
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=10.0, upper_bound=13.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=8.0, peak=10.0, upper_bound=12.0),
            ),
            ExpertOpinion(
                expert_id="E4",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=10.0, upper_bound=11.0),
            ),
        ]

        # WHEN
        result = calculator.calculate_median(opinions)

        # THEN: the two middle opinions of the list (E2 and E3) are averaged
        assert result.lower_bound == 7.5
        assert result.peak == 10.0
        assert result.upper_bound == 12.5

    def test_clustered_centroids_near_median(self, calculator):
        """Multiple opinions clustered near median centroid."""
        # GIVEN: 6 experts: E1(centroid=2), E2-E5(centroid=10), E6(centroid=19)
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=10.0, upper_bound=11.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=9.5, peak=10.0, upper_bound=10.5),
            ),
            ExpertOpinion(
                expert_id="E4",
                opinion=FuzzyTriangleNumber(lower_bound=9.8, peak=10.0, upper_bound=10.2),
            ),
            ExpertOpinion(
                expert_id="E5",
                opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=10.0, upper_bound=10.0),
            ),
            ExpertOpinion(
                expert_id="E6",
                opinion=FuzzyTriangleNumber(lower_bound=18.0, peak=19.0, upper_bound=20.0),
            ),
        ]

        # WHEN
        result = calculator.calculate_median(opinions)

        # THEN: the two middle opinions (E3 and E4) are averaged
        assert result.lower_bound == 9.65
        assert result.peak == 10.0
        assert result.upper_bound == 10.35

    def test_three_experts_all_same_centroid(self, calculator):
        """Three experts all with identical centroids."""
        # GIVEN: all have centroid = 10.0
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=10.0, upper_bound=13.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=10.0, upper_bound=11.0),
            ),
        ]

        # WHEN
        result = calculator.calculate_median(opinions)

        # THEN: the middle element of the list (E2) is the median
        assert result.lower_bound == 7.0
        assert result.peak == 10.0
        assert result.upper_bound == 13.0
