"""
Unit tests for FuzzyTriangleNumber class.
"""

import pytest

from src.models.fuzzy_number import FuzzyTriangleNumber


class TestFuzzyTriangleNumberCreation:
    """Test cases for FuzzyTriangleNumber object creation."""

    def test_valid_creation(self, standard_fuzzy):
        """Test creating a valid fuzzy triangular number."""
        # GIVEN - Fixture provides standard fuzzy number

        # WHEN - Already created by fixture

        # THEN - Verify all attributes are set correctly
        assert standard_fuzzy.lower_bound == 5.0, (
            f"Expected lower_bound to be 5.0, got {standard_fuzzy.lower_bound}"
        )
        assert standard_fuzzy.peak == 10.0, f"Expected peak to be 10.0, got {standard_fuzzy.peak}"
        assert standard_fuzzy.upper_bound == 15.0, (
            f"Expected upper_bound to be 15.0, got {standard_fuzzy.upper_bound}"
        )

    def test_creation_with_equal_values(self, equal_values_fuzzy):
        """Test creating fuzzy number where all three values are equal."""
        # GIVEN - Fixture provides fuzzy number with equal values

        # WHEN - Already created by fixture

        # THEN - Verify all values are equal
        assert equal_values_fuzzy.lower_bound == 10.0, (
            f"Expected lower_bound to be 10.0, got {equal_values_fuzzy.lower_bound}"
        )
        assert equal_values_fuzzy.peak == 10.0, (
            f"Expected peak to be 10.0, got {equal_values_fuzzy.peak}"
        )
        assert equal_values_fuzzy.upper_bound == 10.0, (
            f"Expected upper_bound to be 10.0, got {equal_values_fuzzy.upper_bound}"
        )

    def test_creation_lower_equals_peak(self):
        """Test creating fuzzy number where lower_bound equals peak."""
        # GIVEN - Parameters where lower_bound equals peak
        lower = 5.0
        peak = 5.0
        upper = 10.0

        # WHEN - Create fuzzy number
        fuzzy = FuzzyTriangleNumber(lower_bound=lower, peak=peak, upper_bound=upper)

        # THEN - Verify attributes are set correctly
        assert fuzzy.lower_bound == 5.0, f"Expected lower_bound to be 5.0, got {fuzzy.lower_bound}"
        assert fuzzy.peak == 5.0, f"Expected peak to be 5.0, got {fuzzy.peak}"
        assert fuzzy.upper_bound == 10.0, (
            f"Expected upper_bound to be 10.0, got {fuzzy.upper_bound}"
        )

    def test_creation_peak_equals_upper(self):
        """Test creating fuzzy number where peak equals upper_bound."""
        # GIVEN - Parameters where peak equals upper_bound
        lower = 5.0
        peak = 10.0
        upper = 10.0

        # WHEN - Create fuzzy number
        fuzzy = FuzzyTriangleNumber(lower_bound=lower, peak=peak, upper_bound=upper)

        # THEN - Verify attributes are set correctly
        assert fuzzy.lower_bound == 5.0, f"Expected lower_bound to be 5.0, got {fuzzy.lower_bound}"
        assert fuzzy.peak == 10.0, f"Expected peak to be 10.0, got {fuzzy.peak}"
        assert fuzzy.upper_bound == 10.0, (
            f"Expected upper_bound to be 10.0, got {fuzzy.upper_bound}"
        )


class TestFuzzyTriangleNumberValidation:
    """Test cases for input validation."""

    def test_peak_less_than_lower_raises_error(self):
        """Test that peak < lower_bound raises ValueError."""
        # GIVEN - Invalid parameters where peak < lower_bound
        invalid_lower = 10.0
        invalid_peak = 5.0
        invalid_upper = 15.0

        # WHEN/THEN - Attempt to create fuzzy number should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            FuzzyTriangleNumber(
                lower_bound=invalid_lower, peak=invalid_peak, upper_bound=invalid_upper
            )

        assert "lower_bound <= peak <= upper_bound" in str(exc_info.value), (
            f"Expected error message to contain constraint description, got: {exc_info.value}"
        )

    def test_upper_less_than_peak_raises_error(self):
        """Test that upper_bound < peak raises ValueError."""
        # GIVEN - Invalid parameters where upper_bound < peak
        invalid_lower = 5.0
        invalid_peak = 15.0
        invalid_upper = 10.0

        # WHEN/THEN - Attempt to create fuzzy number should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            FuzzyTriangleNumber(
                lower_bound=invalid_lower, peak=invalid_peak, upper_bound=invalid_upper
            )

        assert "lower_bound <= peak <= upper_bound" in str(exc_info.value), (
            f"Expected error message to contain constraint description, got: {exc_info.value}"
        )

    def test_upper_less_than_lower_raises_error(self):
        """Test that upper_bound < lower_bound raises ValueError."""
        # GIVEN - Invalid parameters where upper_bound < lower_bound
        invalid_lower = 15.0
        invalid_peak = 10.0
        invalid_upper = 5.0

        # WHEN/THEN - Attempt to create fuzzy number should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            FuzzyTriangleNumber(
                lower_bound=invalid_lower, peak=invalid_peak, upper_bound=invalid_upper
            )

        assert "lower_bound <= peak <= upper_bound" in str(exc_info.value), (
            f"Expected error message to contain constraint description, got: {exc_info.value}"
        )

    def test_all_values_inverted_raises_error(self):
        """Test that completely inverted values raise ValueError."""
        # GIVEN - Completely inverted values
        invalid_lower = 20.0
        invalid_peak = 10.0
        invalid_upper = 5.0

        # WHEN/THEN - Attempt to create fuzzy number should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            FuzzyTriangleNumber(
                lower_bound=invalid_lower, peak=invalid_peak, upper_bound=invalid_upper
            )

        assert "lower_bound <= peak <= upper_bound" in str(exc_info.value), (
            f"Expected error message to contain constraint description, got: {exc_info.value}"
        )


class TestFuzzyTriangleNumberCentroid:
    """Test cases for centroid calculation."""

    def test_centroid_calculation(self, standard_fuzzy):
        """Test centroid calculation with normal values."""
        # GIVEN - Standard fuzzy number (5.0, 10.0, 15.0) from fixture

        # WHEN - Access centroid property
        centroid = standard_fuzzy.centroid

        # THEN - Verify centroid is calculated correctly
        expected_centroid = (5.0 + 10.0 + 15.0) / 3.0
        assert centroid == expected_centroid, (
            f"Expected centroid to be {expected_centroid}, got {centroid}"
        )
        assert centroid == 10.0, f"Expected centroid to be 10.0, got {centroid}"

    def test_centroid_with_equal_values(self, equal_values_fuzzy):
        """Test centroid when all values are equal."""
        # GIVEN - Fuzzy number with equal values (10.0, 10.0, 10.0) from fixture

        # WHEN - Access centroid property
        centroid = equal_values_fuzzy.centroid

        # THEN - Verify centroid equals the common value
        assert centroid == 10.0, f"Expected centroid to be 10.0, got {centroid}"

    def test_centroid_with_decimals(self):
        """Test centroid calculation with decimal values."""
        # GIVEN - Fuzzy number with decimal values
        fuzzy = FuzzyTriangleNumber(lower_bound=6.5, peak=8.3, upper_bound=11.2)
        expected_centroid = (6.5 + 8.3 + 11.2) / 3.0

        # WHEN - Access centroid property
        centroid = fuzzy.centroid

        # THEN - Verify centroid is calculated with high precision
        assert abs(centroid - expected_centroid) < 1e-10, (
            f"Expected centroid to be {expected_centroid}, got {centroid}"
        )

    def test_centroid_from_excel_example(self):
        """Test centroid with values from Excel reference."""
        # GIVEN - Project manager from Excel: best=15, lower=10, upper=15
        fuzzy = FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=15.0)
        expected_centroid = (10.0 + 15.0 + 15.0) / 3.0

        # WHEN - Access centroid property
        centroid = fuzzy.centroid

        # THEN - Verify centroid matches Excel calculation
        assert abs(centroid - expected_centroid) < 1e-10, (
            f"Expected centroid to be {expected_centroid}, got {centroid}"
        )
        assert abs(centroid - 13.333333333333334) < 1e-10, (
            f"Expected centroid to be 13.333333333333334, got {centroid}"
        )


class TestFuzzyTriangleNumberStringRepresentation:
    """Test cases for string representations."""

    def test_str_representation(self, standard_fuzzy):
        """Test __str__ method."""
        # GIVEN - Standard fuzzy number from fixture

        # WHEN - Convert to string
        str_repr = str(standard_fuzzy)

        # THEN - Verify formatted string representation
        assert str_repr == "(5.00, 10.00, 15.00)", (
            f"Expected str to be '(5.00, 10.00, 15.00)', got '{str_repr}'"
        )

    def test_repr_representation(self, standard_fuzzy):
        """Test __repr__ method (dataclass auto-generated)."""
        # GIVEN - Standard fuzzy number from fixture

        # WHEN - Get repr representation
        repr_str = repr(standard_fuzzy)

        # THEN - Verify repr contains class name and all attributes
        assert "FuzzyTriangleNumber" in repr_str, (
            f"Expected 'FuzzyTriangleNumber' in repr, got: {repr_str}"
        )
        assert "lower_bound=5.0" in repr_str, f"Expected 'lower_bound=5.0' in repr, got: {repr_str}"
        assert "peak=10.0" in repr_str, f"Expected 'peak=10.0' in repr, got: {repr_str}"
        assert "upper_bound=15.0" in repr_str, (
            f"Expected 'upper_bound=15.0' in repr, got: {repr_str}"
        )

    def test_repr_can_recreate_object(self, standard_fuzzy):
        """Test that repr contains enough information to understand the object."""
        # GIVEN - Standard fuzzy number from fixture

        # WHEN - Get repr representation
        repr_str = repr(standard_fuzzy)

        # THEN - Verify repr contains all necessary information
        assert "FuzzyTriangleNumber" in repr_str, f"Expected class name in repr, got: {repr_str}"
        assert "5.0" in repr_str, f"Expected '5.0' in repr, got: {repr_str}"
        assert "10.0" in repr_str, f"Expected '10.0' in repr, got: {repr_str}"
        assert "15.0" in repr_str, f"Expected '15.0' in repr, got: {repr_str}"


class TestFuzzyTriangleNumberImmutability:
    """Test cases for immutability (frozen dataclass)."""

    @pytest.mark.parametrize(
        "attribute_name",
        ["lower_bound", "peak", "upper_bound"],
        ids=["frozen_lower_bound", "frozen_peak", "frozen_upper_bound"],
    )
    def test_frozen_attributes(self, standard_fuzzy, attribute_name):
        """Test that all attributes cannot be modified after creation.

        This parametrized test verifies immutability of all three
        FuzzyTriangleNumber attributes, following DRY principle.
        """
        # GIVEN - Standard fuzzy number from fixture

        # WHEN/THEN - Attempt to modify attribute should raise error
        with pytest.raises((AttributeError, TypeError)) as exc_info:
            setattr(standard_fuzzy, attribute_name, 20.0)

        # Verify appropriate error was raised
        assert exc_info.value is not None, (
            f"Expected AttributeError or TypeError when modifying {attribute_name}"
        )

    def test_delattr_raises_error(self, standard_fuzzy):
        """Test that deleting attributes is prevented."""
        # GIVEN - Standard fuzzy number from fixture

        # WHEN/THEN - Attempt to delete attribute should raise AttributeError
        with pytest.raises(AttributeError) as exc_info:
            del standard_fuzzy.lower_bound

        assert "Cannot delete immutable FuzzyTriangleNumber attribute" in str(exc_info.value), (
            f"Expected specific error message, got: {exc_info.value}"
        )

    def test_immutable_value_object(self):
        """Test that FuzzyTriangleNumber behaves as immutable value object."""
        # GIVEN - Two fuzzy numbers with identical values
        fuzzy1 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        fuzzy2 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)

        # WHEN - Compare them

        # THEN - Same values should create equal objects
        assert fuzzy1 == fuzzy2, "Expected fuzzy numbers with same values to be equal"
        # THEN - But they are different instances
        assert fuzzy1 is not fuzzy2, "Expected different object instances"

    def test_hashable_for_use_in_sets(self):
        """Test that frozen FuzzyTriangleNumber is hashable."""
        # GIVEN - Three fuzzy numbers (two identical, one different)
        fuzzy1 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        fuzzy2 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        fuzzy3 = FuzzyTriangleNumber(lower_bound=6.0, peak=11.0, upper_bound=16.0)

        # WHEN - Create a set with these fuzzy numbers
        fuzzy_set = {fuzzy1, fuzzy2, fuzzy3}

        # THEN - Set should contain only 2 unique items (fuzzy1 and fuzzy2 are equal)
        assert len(fuzzy_set) == 2, (
            f"Expected set to have 2 elements (fuzzy1==fuzzy2 are duplicates), got {len(fuzzy_set)}"
        )


class TestFuzzyTriangleNumberEquality:
    """Test cases for equality comparison."""

    def test_equality_with_same_values(self):
        """Test that two fuzzy numbers with same values are equal."""
        # GIVEN - Two fuzzy numbers with identical values
        fuzzy1 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        fuzzy2 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)

        # WHEN - Compare them with ==

        # THEN - They should be equal
        assert fuzzy1 == fuzzy2, "Expected fuzzy numbers with same values to be equal"

    def test_equality_with_non_fuzzy_number_returns_false(self, standard_fuzzy):
        """Test that comparison with non-FuzzyTriangleNumber returns False."""
        # GIVEN - Standard fuzzy number and various non-FuzzyTriangleNumber objects

        # WHEN/THEN - Compare with different types should return False
        assert standard_fuzzy != (5.0, 10.0, 15.0), "Expected fuzzy number to not equal tuple"
        assert standard_fuzzy != [5.0, 10.0, 15.0], "Expected fuzzy number to not equal list"
        assert standard_fuzzy != "5.0, 10.0, 15.0", "Expected fuzzy number to not equal string"
        assert standard_fuzzy != 10.0, "Expected fuzzy number to not equal float"
        assert standard_fuzzy is not None, "Expected fuzzy number to not be None"


class TestFuzzyTriangleNumberAverage:
    """Test cases for static average method."""

    def test_average_two_fuzzy_numbers(self):
        """Test averaging two fuzzy numbers."""
        # GIVEN - Two fuzzy numbers to average
        fn1 = FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0)
        fn2 = FuzzyTriangleNumber(lower_bound=12.0, peak=18.0, upper_bound=22.0)

        # WHEN - Calculate average
        result = FuzzyTriangleNumber.average([fn1, fn2])

        # THEN - Verify average calculated correctly for each component
        assert result.lower_bound == 11.0, (
            f"Expected average lower_bound to be 11.0, got {result.lower_bound}"
        )
        assert result.peak == 16.5, f"Expected average peak to be 16.5, got {result.peak}"
        assert result.upper_bound == 21.0, (
            f"Expected average upper_bound to be 21.0, got {result.upper_bound}"
        )

    def test_average_empty_list_raises_error(self):
        """Test that averaging empty list raises ValueError."""
        # GIVEN - Empty list of fuzzy numbers

        # WHEN/THEN - Attempt to average should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            FuzzyTriangleNumber.average([])

        assert "Cannot average empty list of fuzzy numbers" in str(exc_info.value), (
            f"Expected specific error message, got: {exc_info.value}"
        )
