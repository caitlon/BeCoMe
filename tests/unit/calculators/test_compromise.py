"""Unit tests for BeCoMe compromise calculation."""

import pytest

from src.exceptions import EmptyOpinionsError
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture
def five_experts_skewed_opinions():
    """Provide opinions with skewed distribution for testing mean-median divergence.

    :return: List of 5 ExpertOpinion instances with outliers
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
    """Provide opinions for testing max error calculation.

    :return: List of 2 ExpertOpinion instances with different ranges
    """
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
    """Test cases for full BeCoMe compromise calculation."""

    def test_compromise_with_three_experts_odd(self, calculator, three_experts_opinions):
        """Test compromise with three experts returns zero error for sequential data."""
        # WHEN
        result = calculator.calculate_compromise(three_experts_opinions)

        # THEN
        assert result.num_experts == 3
        assert result.is_even is False

        assert result.arithmetic_mean.lower_bound == 6.0
        assert result.arithmetic_mean.peak == 9.0
        assert result.arithmetic_mean.upper_bound == 12.0

        assert result.median.lower_bound == 6.0
        assert result.median.peak == 9.0
        assert result.median.upper_bound == 12.0

        assert result.best_compromise.lower_bound == 6.0
        assert result.best_compromise.peak == 9.0
        assert result.best_compromise.upper_bound == 12.0

        assert result.max_error == 0.0

    def test_compromise_with_four_experts_even(self, calculator, four_experts_even_opinions):
        """Test compromise with four experts returns zero error for sequential data."""
        # WHEN
        result = calculator.calculate_compromise(four_experts_even_opinions)

        # THEN
        assert result.num_experts == 4
        assert result.is_even is True

        assert result.best_compromise.lower_bound == 5.5
        assert result.best_compromise.peak == 6.5
        assert result.best_compromise.upper_bound == 7.5

        assert result.max_error == 0.0

    def test_compromise_with_skewed_data(self, calculator, five_experts_skewed_opinions):
        """Test compromise with skewed data produces non-zero error."""
        # WHEN
        result = calculator.calculate_compromise(five_experts_skewed_opinions)

        # THEN
        assert result.arithmetic_mean.lower_bound == 5.4
        assert result.arithmetic_mean.peak == 6.4
        assert result.arithmetic_mean.upper_bound == 7.4

        assert result.median.lower_bound == 3.0
        assert result.median.peak == 4.0
        assert result.median.upper_bound == 5.0

        assert result.best_compromise.lower_bound == 4.2
        assert result.best_compromise.peak == 5.2
        assert result.best_compromise.upper_bound == 6.2

        assert abs(result.max_error - 1.2) < 1e-10

    def test_compromise_with_single_expert(self, calculator, single_expert_opinion):
        """Test compromise with single expert returns same values for all aggregations."""
        # WHEN
        result = calculator.calculate_compromise(single_expert_opinion)

        # THEN
        assert result.num_experts == 1
        assert result.is_even is False

        assert result.arithmetic_mean.lower_bound == 5.0
        assert result.arithmetic_mean.peak == 10.0
        assert result.arithmetic_mean.upper_bound == 15.0

        assert result.median.lower_bound == 5.0
        assert result.median.peak == 10.0
        assert result.median.upper_bound == 15.0

        assert result.best_compromise.lower_bound == 5.0
        assert result.best_compromise.peak == 10.0
        assert result.best_compromise.upper_bound == 15.0

        assert result.max_error == 0.0

    def test_compromise_empty_list_raises_error(self, calculator):
        """Test that empty opinions list raises EmptyOpinionsError."""
        # WHEN / THEN
        with pytest.raises(EmptyOpinionsError) as exc_info:
            calculator.calculate_compromise([])

        assert "empty" in str(exc_info.value).lower()

    def test_compromise_max_error_calculation(self, calculator, two_experts_for_error_calculation):
        """Test that max_error equals half the distance between mean and median centroids."""
        # WHEN
        result = calculator.calculate_compromise(two_experts_for_error_calculation)

        # THEN
        mean_centroid = result.arithmetic_mean.centroid
        median_centroid = result.median.centroid
        expected_error = abs(mean_centroid - median_centroid) / 2

        assert abs(result.max_error - expected_error) < 1e-10


class TestBeCoMeCalculatorEdgeCases:
    """Edge cases and stress tests for BeCoMe calculator."""

    def test_all_identical_opinions(self, calculator):
        """All experts with identical opinions produces zero error."""
        # GIVEN
        opinions = [
            ExpertOpinion(
                expert_id=f"E{i}",
                opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            )
            for i in range(10)
        ]

        # WHEN
        result = calculator.calculate_compromise(opinions)

        # THEN
        assert result.max_error == 0.0
        assert result.best_compromise.lower_bound == 5.0
        assert result.best_compromise.peak == 10.0
        assert result.best_compromise.upper_bound == 15.0
        assert result.num_experts == 10

    def test_two_experts_minimum_for_even(self, calculator):
        """Two experts is minimum for even median strategy."""
        # GIVEN
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=0.0, peak=5.0, upper_bound=10.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0),
            ),
        ]

        # WHEN
        result = calculator.calculate_compromise(opinions)

        # THEN
        assert result.num_experts == 2
        assert result.is_even is True
        assert result.arithmetic_mean.lower_bound == 5.0
        assert result.arithmetic_mean.peak == 10.0
        assert result.arithmetic_mean.upper_bound == 15.0
        # Median is average of both (same as mean for 2 experts)
        assert result.median.lower_bound == 5.0
        assert result.median.peak == 10.0
        assert result.median.upper_bound == 15.0

    def test_reverse_sorted_opinions_same_result(self, calculator):
        """Opinions given in reverse order should produce same result."""
        # GIVEN
        forward = [
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
        ]
        reverse = list(reversed(forward))

        # WHEN
        result_forward = calculator.calculate_compromise(forward)
        result_reverse = calculator.calculate_compromise(reverse)

        # THEN
        assert result_forward.best_compromise == result_reverse.best_compromise
        assert result_forward.max_error == result_reverse.max_error
        assert result_forward.arithmetic_mean == result_reverse.arithmetic_mean
        assert result_forward.median == result_reverse.median

    def test_large_number_of_experts(self, calculator):
        """Calculator should handle 1000 experts without issues."""
        # GIVEN
        opinions = [
            ExpertOpinion(
                expert_id=f"E{i}",
                opinion=FuzzyTriangleNumber(
                    lower_bound=float(i), peak=float(i + 5), upper_bound=float(i + 10)
                ),
            )
            for i in range(1000)
        ]

        # WHEN
        result = calculator.calculate_compromise(opinions)

        # THEN
        assert result.num_experts == 1000
        assert result.is_even is True
        assert result.best_compromise is not None
        # Mean of 0..999 is 499.5
        assert result.arithmetic_mean.lower_bound == pytest.approx(499.5, rel=1e-10)

    def test_negative_values_handled_correctly(self, calculator):
        """Negative fuzzy values should be processed correctly."""
        # GIVEN
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=-30.0, peak=-20.0, upper_bound=-10.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=-20.0, peak=-10.0, upper_bound=0.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=-10.0, peak=0.0, upper_bound=10.0),
            ),
        ]

        # WHEN
        result = calculator.calculate_compromise(opinions)

        # THEN
        assert result.num_experts == 3
        assert result.arithmetic_mean.peak == -10.0
        assert result.median.peak == -10.0
        assert result.best_compromise.peak == -10.0

    def test_zero_spread_opinions(self, calculator):
        """Degenerate triangles (lower=peak=upper) should work."""
        # GIVEN
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=10.0, upper_bound=10.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=20.0, peak=20.0, upper_bound=20.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=30.0, peak=30.0, upper_bound=30.0),
            ),
        ]

        # WHEN
        result = calculator.calculate_compromise(opinions)

        # THEN
        assert result.arithmetic_mean.lower_bound == 20.0
        assert result.arithmetic_mean.peak == 20.0
        assert result.arithmetic_mean.upper_bound == 20.0
        assert result.median.peak == 20.0

    def test_extreme_outlier_affects_mean_not_median(self, calculator):
        """Extreme outlier significantly affects mean but not median."""
        # GIVEN - one extreme outlier
        opinions = [
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=12.0, peak=17.0, upper_bound=22.0),
            ),
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=14.0, peak=19.0, upper_bound=24.0),
            ),
            ExpertOpinion(
                expert_id="E4",
                opinion=FuzzyTriangleNumber(lower_bound=16.0, peak=21.0, upper_bound=26.0),
            ),
            ExpertOpinion(
                expert_id="E5",  # Extreme outlier
                opinion=FuzzyTriangleNumber(lower_bound=1000.0, peak=1005.0, upper_bound=1010.0),
            ),
        ]

        # WHEN
        result = calculator.calculate_compromise(opinions)

        # THEN - median is not affected by outlier
        assert result.median.peak == 19.0  # Middle value (E3)
        # Mean is significantly higher due to outlier
        assert result.arithmetic_mean.peak > 200.0
        # Max error is large due to mean-median divergence
        assert result.max_error > 50.0
