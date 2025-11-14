"""Unit tests for FuzzyTriangleNumber class."""

import pytest

from src.models.fuzzy_number import FuzzyTriangleNumber


class TestFuzzyTriangleNumberCreation:
    """Test cases for FuzzyTriangleNumber object creation."""

    def test_valid_creation(self, standard_fuzzy):
        """Test creating a valid fuzzy triangular number."""
        # THEN
        assert standard_fuzzy.lower_bound == 5.0
        assert standard_fuzzy.peak == 10.0
        assert standard_fuzzy.upper_bound == 15.0

    def test_creation_with_equal_values(self, equal_values_fuzzy):
        """Test creating fuzzy number where all three values are equal."""
        # THEN
        assert equal_values_fuzzy.lower_bound == 10.0
        assert equal_values_fuzzy.peak == 10.0
        assert equal_values_fuzzy.upper_bound == 10.0

    def test_creation_lower_equals_peak(self):
        """Test creating fuzzy number where lower_bound equals peak."""
        # GIVEN
        lower = 5.0
        peak = 5.0
        upper = 10.0

        # WHEN
        fuzzy = FuzzyTriangleNumber(lower_bound=lower, peak=peak, upper_bound=upper)

        # THEN
        assert fuzzy.lower_bound == 5.0
        assert fuzzy.peak == 5.0
        assert fuzzy.upper_bound == 10.0

    def test_creation_peak_equals_upper(self):
        """Test creating fuzzy number where peak equals upper_bound."""
        # GIVEN
        lower = 5.0
        peak = 10.0
        upper = 10.0

        # WHEN
        fuzzy = FuzzyTriangleNumber(lower_bound=lower, peak=peak, upper_bound=upper)

        # THEN
        assert fuzzy.lower_bound == 5.0
        assert fuzzy.peak == 10.0
        assert fuzzy.upper_bound == 10.0


class TestFuzzyTriangleNumberValidation:
    """Test cases for input validation."""

    def test_peak_less_than_lower_raises_error(self):
        """Test that peak < lower_bound raises ValueError."""
        # GIVEN
        invalid_lower = 10.0
        invalid_peak = 5.0
        invalid_upper = 15.0

        # WHEN / THEN
        with pytest.raises(ValueError) as exc_info:
            FuzzyTriangleNumber(
                lower_bound=invalid_lower, peak=invalid_peak, upper_bound=invalid_upper
            )

        assert "lower_bound <= peak <= upper_bound" in str(exc_info.value)

    def test_upper_less_than_peak_raises_error(self):
        """Test that upper_bound < peak raises ValueError."""
        # GIVEN
        invalid_lower = 5.0
        invalid_peak = 15.0
        invalid_upper = 10.0

        # WHEN / THEN
        with pytest.raises(ValueError) as exc_info:
            FuzzyTriangleNumber(
                lower_bound=invalid_lower, peak=invalid_peak, upper_bound=invalid_upper
            )

        assert "lower_bound <= peak <= upper_bound" in str(exc_info.value)

    def test_upper_less_than_lower_raises_error(self):
        """Test that upper_bound < lower_bound raises ValueError."""
        # GIVEN
        invalid_lower = 15.0
        invalid_peak = 10.0
        invalid_upper = 5.0

        # WHEN / THEN
        with pytest.raises(ValueError) as exc_info:
            FuzzyTriangleNumber(
                lower_bound=invalid_lower, peak=invalid_peak, upper_bound=invalid_upper
            )

        assert "lower_bound <= peak <= upper_bound" in str(exc_info.value)

    def test_all_values_inverted_raises_error(self):
        """Test that completely inverted values raise ValueError."""
        # GIVEN
        invalid_lower = 20.0
        invalid_peak = 10.0
        invalid_upper = 5.0

        # WHEN / THEN
        with pytest.raises(ValueError) as exc_info:
            FuzzyTriangleNumber(
                lower_bound=invalid_lower, peak=invalid_peak, upper_bound=invalid_upper
            )

        assert "lower_bound <= peak <= upper_bound" in str(exc_info.value)


class TestFuzzyTriangleNumberCentroid:
    """Test cases for centroid calculation."""

    def test_centroid_calculation(self, standard_fuzzy):
        """Test centroid calculation with normal values."""
        # WHEN
        centroid = standard_fuzzy.centroid

        # THEN
        assert centroid == 10.0

    def test_centroid_with_equal_values(self, equal_values_fuzzy):
        """Test centroid when all values are equal."""
        # WHEN
        centroid = equal_values_fuzzy.centroid

        # THEN
        assert centroid == 10.0

    def test_centroid_with_decimals(self):
        """Test centroid calculation with decimal values."""
        # GIVEN
        fuzzy = FuzzyTriangleNumber(lower_bound=6.5, peak=8.3, upper_bound=11.2)

        # WHEN
        centroid = fuzzy.centroid

        # THEN
        assert abs(centroid - 8.666666666666666) < 1e-10

    def test_centroid_from_excel_example(self):
        """Test centroid with values from Excel reference."""
        # GIVEN
        fuzzy = FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=15.0)

        # WHEN
        centroid = fuzzy.centroid

        # THEN
        assert abs(centroid - 13.333333333333334) < 1e-10


class TestFuzzyTriangleNumberStringRepresentation:
    """Test cases for string representations."""

    def test_str_representation(self, standard_fuzzy):
        """Test __str__ method."""
        # WHEN
        str_repr = str(standard_fuzzy)

        # THEN
        assert str_repr == "(5.00, 10.00, 15.00)"

    def test_repr_representation(self, standard_fuzzy):
        """Test __repr__ method."""
        # WHEN
        repr_str = repr(standard_fuzzy)

        # THEN
        assert "FuzzyTriangleNumber" in repr_str
        assert "lower_bound=5.0" in repr_str
        assert "peak=10.0" in repr_str
        assert "upper_bound=15.0" in repr_str

    def test_repr_can_recreate_object(self, standard_fuzzy):
        """Test that repr contains enough information to understand the object."""
        # WHEN
        repr_str = repr(standard_fuzzy)

        # THEN
        assert "FuzzyTriangleNumber" in repr_str
        assert "5.0" in repr_str
        assert "10.0" in repr_str
        assert "15.0" in repr_str


class TestFuzzyTriangleNumberImmutability:
    """Test cases for immutability (frozen dataclass)."""

    @pytest.mark.parametrize(
        "attribute_name",
        ["lower_bound", "peak", "upper_bound"],
        ids=["frozen_lower_bound", "frozen_peak", "frozen_upper_bound"],
    )
    def test_frozen_attributes(self, standard_fuzzy, attribute_name):
        """Test that all attributes cannot be modified after creation."""
        # WHEN / THEN
        with pytest.raises((AttributeError, TypeError)) as exc_info:
            setattr(standard_fuzzy, attribute_name, 20.0)

        assert exc_info.value is not None

    def test_delattr_raises_error(self, standard_fuzzy):
        """Test that deleting attributes is prevented."""
        # WHEN / THEN
        with pytest.raises(AttributeError) as exc_info:
            del standard_fuzzy.lower_bound

        assert "Cannot delete immutable FuzzyTriangleNumber attribute" in str(exc_info.value)

    def test_immutable_value_object(self):
        """Test that FuzzyTriangleNumber behaves as immutable value object."""
        # GIVEN
        fuzzy1 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        fuzzy2 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)

        # THEN
        assert fuzzy1 == fuzzy2
        assert fuzzy1 is not fuzzy2

    def test_hashable_for_use_in_sets(self):
        """Test that frozen FuzzyTriangleNumber is hashable."""
        # GIVEN
        fuzzy1 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        fuzzy2 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        fuzzy3 = FuzzyTriangleNumber(lower_bound=6.0, peak=11.0, upper_bound=16.0)

        # WHEN
        fuzzy_set = {fuzzy1, fuzzy2, fuzzy3}

        # THEN
        assert len(fuzzy_set) == 2


class TestFuzzyTriangleNumberEquality:
    """Test cases for equality comparison."""

    def test_equality_with_same_values(self):
        """Test that two fuzzy numbers with same values are equal."""
        # GIVEN
        fuzzy1 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        fuzzy2 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)

        # THEN
        assert fuzzy1 == fuzzy2

    def test_equality_with_non_fuzzy_number_returns_false(self, standard_fuzzy):
        """Test that comparison with non-FuzzyTriangleNumber returns False."""
        # WHEN / THEN
        assert standard_fuzzy != (5.0, 10.0, 15.0)
        assert standard_fuzzy != [5.0, 10.0, 15.0]
        assert standard_fuzzy != "5.0, 10.0, 15.0"
        assert standard_fuzzy != 10.0
        assert standard_fuzzy is not None


class TestFuzzyTriangleNumberAverage:
    """Test cases for static average method."""

    def test_average_two_fuzzy_numbers(self):
        """Test averaging two fuzzy numbers."""
        # GIVEN
        fn1 = FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0)
        fn2 = FuzzyTriangleNumber(lower_bound=12.0, peak=18.0, upper_bound=22.0)

        # WHEN
        result = FuzzyTriangleNumber.average([fn1, fn2])

        # THEN
        assert result.lower_bound == 11.0
        assert result.peak == 16.5
        assert result.upper_bound == 21.0

    def test_average_empty_list_raises_error(self):
        """Test that averaging empty list raises ValueError."""
        # WHEN / THEN
        with pytest.raises(ValueError) as exc_info:
            FuzzyTriangleNumber.average([])

        assert "Cannot average empty list of fuzzy numbers" in str(exc_info.value)
