"""Property-based tests for FuzzyTriangleNumber invariants.

Verifies mathematical properties that hold for all valid fuzzy
triangular numbers, complementing the example-based tests in
test_fuzzy_number.py.
"""

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.models.fuzzy_number import FuzzyTriangleNumber
from tests.unit.strategies import fuzzy_numbers


class TestFuzzyNumberCentroidProperty:
    """Property tests for centroid calculation invariants."""

    @given(fn=fuzzy_numbers())
    def test_centroid_equals_component_average(self, fn: FuzzyTriangleNumber) -> None:
        """Centroid always equals (a + c + b) / 3 for any valid input."""
        # GIVEN - a valid fuzzy triangular number

        # WHEN
        centroid = fn.centroid

        # THEN
        expected = (fn.lower_bound + fn.peak + fn.upper_bound) / 3.0
        assert centroid == pytest.approx(expected, rel=1e-9)

    @given(fn=fuzzy_numbers())
    def test_centroid_between_lower_and_upper(self, fn: FuzzyTriangleNumber) -> None:
        """Centroid is always within [lower_bound, upper_bound] (up to float rounding)."""
        # GIVEN - a valid fuzzy triangular number

        # WHEN
        centroid = fn.centroid

        # THEN — allow tiny floating-point rounding error from (a+c+b)/3
        eps = 1e-9
        assert fn.lower_bound - eps <= centroid <= fn.upper_bound + eps

    @given(value=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
    def test_equal_components_centroid_equals_value(self, value: float) -> None:
        """When all three components are equal, centroid equals that value."""
        # GIVEN - a degenerate fuzzy number where a == c == b
        fn = FuzzyTriangleNumber(lower_bound=value, peak=value, upper_bound=value)

        # WHEN
        centroid = fn.centroid

        # THEN
        assert centroid == pytest.approx(value, rel=1e-9)


class TestFuzzyNumberAverageProperties:
    """Property tests for the static average method."""

    @given(fn1=fuzzy_numbers(), fn2=fuzzy_numbers())
    def test_average_commutativity(
        self, fn1: FuzzyTriangleNumber, fn2: FuzzyTriangleNumber
    ) -> None:
        """Average of two fuzzy numbers is the same regardless of order."""
        # GIVEN - two valid fuzzy triangular numbers

        # WHEN
        avg_forward = FuzzyTriangleNumber.average([fn1, fn2])
        avg_backward = FuzzyTriangleNumber.average([fn2, fn1])

        # THEN
        assert avg_forward == avg_backward

    @given(fns=st.lists(fuzzy_numbers(), min_size=2, max_size=10))
    @settings(max_examples=50)
    def test_average_preserves_ordering_constraint(self, fns: list[FuzzyTriangleNumber]) -> None:
        """Average preserves the triangular constraint lower <= peak <= upper."""
        # GIVEN - a list of valid fuzzy triangular numbers

        # WHEN
        result = FuzzyTriangleNumber.average(fns)

        # THEN
        assert result.lower_bound <= result.peak <= result.upper_bound

    @given(fn=fuzzy_numbers())
    def test_average_single_element_is_identity(self, fn: FuzzyTriangleNumber) -> None:
        """Average of a single-element list returns the same values."""
        # GIVEN - a single fuzzy triangular number

        # WHEN
        result = FuzzyTriangleNumber.average([fn])

        # THEN
        assert result.lower_bound == pytest.approx(fn.lower_bound, rel=1e-9)
        assert result.peak == pytest.approx(fn.peak, rel=1e-9)
        assert result.upper_bound == pytest.approx(fn.upper_bound, rel=1e-9)

    @given(fn=fuzzy_numbers(), count=st.integers(min_value=2, max_value=10))
    def test_average_of_identical_equals_element(self, fn: FuzzyTriangleNumber, count: int) -> None:
        """Average of identical fuzzy numbers equals the original."""
        # GIVEN - a list of identical fuzzy numbers
        identical = [fn] * count

        # WHEN
        result = FuzzyTriangleNumber.average(identical)

        # THEN
        assert result.lower_bound == pytest.approx(fn.lower_bound, rel=1e-9)
        assert result.peak == pytest.approx(fn.peak, rel=1e-9)
        assert result.upper_bound == pytest.approx(fn.upper_bound, rel=1e-9)

    @given(fns=st.lists(fuzzy_numbers(), min_size=3, max_size=8), data=st.data())
    @settings(max_examples=50)
    def test_average_independent_of_order(
        self, fns: list[FuzzyTriangleNumber], data: st.DataObject
    ) -> None:
        """Average is independent of the input list ordering."""
        # GIVEN - a list of fuzzy numbers and a random permutation
        shuffled = list(fns)
        seed = data.draw(st.integers(min_value=0, max_value=2**31))
        random.Random(seed).shuffle(shuffled)

        # WHEN
        result_original = FuzzyTriangleNumber.average(fns)
        result_shuffled = FuzzyTriangleNumber.average(shuffled)

        # THEN
        assert result_original == result_shuffled


class TestFuzzyNumberHashConsistency:
    """Property tests for hash/equality contract."""

    @given(fn=fuzzy_numbers())
    def test_hash_consistent_with_equality(self, fn: FuzzyTriangleNumber) -> None:
        """Two equal FuzzyTriangleNumber instances have the same hash."""
        # GIVEN - a fuzzy number and a copy with the same values
        copy = FuzzyTriangleNumber(
            lower_bound=fn.lower_bound, peak=fn.peak, upper_bound=fn.upper_bound
        )

        # WHEN / THEN
        assert fn == copy
        assert hash(fn) == hash(copy)
