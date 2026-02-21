"""Property-based tests for BeCoMeCalculator invariants.

Verifies mathematical properties that hold for all valid expert
opinion sets, complementing the example-based tests in the
calculators test suite.
"""

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber
from tests.unit.strategies import expert_opinions, identical_expert_opinions


class TestCalculatorMedianStability:
    """Median and compromise results are independent of input ordering."""

    @given(opinions=expert_opinions(min_size=2, max_size=10), data=st.data())
    @settings(max_examples=50)
    def test_median_independent_of_input_order(self, calculator, opinions, data) -> None:
        """Median is the same regardless of how opinions are ordered."""
        # GIVEN - a list of expert opinions and a random permutation
        shuffled = list(opinions)
        seed = data.draw(st.integers(min_value=0, max_value=2**31))
        random.Random(seed).shuffle(shuffled)

        # WHEN
        result_original = calculator.calculate_median(opinions)
        result_shuffled = calculator.calculate_median(shuffled)

        # THEN
        assert result_original == result_shuffled

    @given(opinions=expert_opinions(min_size=2, max_size=10), data=st.data())
    @settings(max_examples=50)
    def test_compromise_independent_of_input_order(self, calculator, opinions, data) -> None:
        """Full compromise result is the same regardless of input ordering."""
        # GIVEN - a list of expert opinions and a random permutation
        shuffled = list(opinions)
        seed = data.draw(st.integers(min_value=0, max_value=2**31))
        random.Random(seed).shuffle(shuffled)

        # WHEN
        result_original = calculator.calculate_compromise(opinions)
        result_shuffled = calculator.calculate_compromise(shuffled)

        # THEN
        assert result_original.best_compromise == result_shuffled.best_compromise
        assert result_original.arithmetic_mean == result_shuffled.arithmetic_mean
        assert result_original.median == result_shuffled.median
        assert result_original.max_error == pytest.approx(result_shuffled.max_error, rel=1e-9)


class TestCalculatorIdenticalExperts:
    """When all experts share the same opinion, aggregations converge."""

    @given(opinions=identical_expert_opinions(min_size=2, max_size=10))
    def test_identical_experts_zero_error(self, calculator, opinions) -> None:
        """Max error is zero when all experts agree."""
        # GIVEN - a set of identical expert opinions

        # WHEN
        result = calculator.calculate_compromise(opinions)

        # THEN
        assert result.max_error == pytest.approx(0.0, abs=1e-9)

    @given(opinions=identical_expert_opinions(min_size=2, max_size=10))
    def test_identical_experts_all_aggregations_equal(self, calculator, opinions) -> None:
        """Best compromise, mean, and median are all equal to the shared opinion."""
        # GIVEN - a set of identical expert opinions
        shared = opinions[0].opinion

        # WHEN
        result = calculator.calculate_compromise(opinions)

        # THEN — all aggregations should reproduce the shared fuzzy number
        for aggregation in (result.best_compromise, result.arithmetic_mean, result.median):
            assert aggregation.lower_bound == pytest.approx(shared.lower_bound, rel=1e-9)
            assert aggregation.peak == pytest.approx(shared.peak, rel=1e-9)
            assert aggregation.upper_bound == pytest.approx(shared.upper_bound, rel=1e-9)


class TestCalculatorMonotonicity:
    """Adding a higher-valued expert shifts the arithmetic mean upward."""

    @given(opinions=expert_opinions(min_size=2, max_size=8))
    @settings(max_examples=50)
    def test_adding_higher_expert_shifts_mean_upward(self, calculator, opinions) -> None:
        """An extra expert above the current mean raises every component."""
        # GIVEN - existing opinions and their arithmetic mean
        current_mean = calculator.calculate_arithmetic_mean(opinions)

        # Create a new expert strictly above the current mean
        new_fn = FuzzyTriangleNumber(
            lower_bound=current_mean.upper_bound + 1.0,
            peak=current_mean.upper_bound + 2.0,
            upper_bound=current_mean.upper_bound + 3.0,
        )
        extended = [*opinions, ExpertOpinion(expert_id="E_new", opinion=new_fn)]

        # WHEN
        new_mean = calculator.calculate_arithmetic_mean(extended)

        # THEN — each component of the new mean is strictly greater
        assert new_mean.lower_bound > current_mean.lower_bound
        assert new_mean.peak > current_mean.peak
        assert new_mean.upper_bound > current_mean.upper_bound


class TestCalculatorConstraintPreservation:
    """All calculator outputs preserve the fuzzy triangular constraint."""

    @given(opinions=expert_opinions(min_size=1, max_size=15))
    @settings(max_examples=50)
    def test_arithmetic_mean_preserves_constraint(self, calculator, opinions) -> None:
        """Arithmetic mean satisfies lower <= peak <= upper."""
        # GIVEN - a list of expert opinions

        # WHEN
        result = calculator.calculate_arithmetic_mean(opinions)

        # THEN
        assert result.lower_bound <= result.peak <= result.upper_bound

    @given(opinions=expert_opinions(min_size=1, max_size=15))
    @settings(max_examples=50)
    def test_median_preserves_constraint(self, calculator, opinions) -> None:
        """Median satisfies lower <= peak <= upper."""
        # GIVEN - a list of expert opinions

        # WHEN
        result = calculator.calculate_median(opinions)

        # THEN
        assert result.lower_bound <= result.peak <= result.upper_bound

    @given(opinions=expert_opinions(min_size=1, max_size=15))
    @settings(max_examples=50)
    def test_best_compromise_preserves_constraint(self, calculator, opinions) -> None:
        """Best compromise satisfies lower <= peak <= upper."""
        # GIVEN - a list of expert opinions

        # WHEN
        result = calculator.calculate_compromise(opinions)

        # THEN
        bc = result.best_compromise
        assert bc.lower_bound <= bc.peak <= bc.upper_bound

    @given(opinions=expert_opinions(min_size=1, max_size=15))
    @settings(max_examples=50)
    def test_max_error_non_negative(self, calculator, opinions) -> None:
        """Max error is always non-negative."""
        # GIVEN - a list of expert opinions

        # WHEN
        result = calculator.calculate_compromise(opinions)

        # THEN
        assert result.max_error >= 0.0
