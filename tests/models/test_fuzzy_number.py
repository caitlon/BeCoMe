"""
Unit tests for FuzzyTriangleNumber class.
"""

import pytest

from src.models.fuzzy_number import FuzzyTriangleNumber


class TestFuzzyTriangleNumberCreation:
    """Test cases for FuzzyTriangleNumber object creation."""

    def test_valid_creation(self):
        """Test creating a valid fuzzy triangular number."""
        fuzzy = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)

        assert fuzzy.lower_bound == 5.0
        assert fuzzy.peak == 10.0
        assert fuzzy.upper_bound == 15.0

    def test_creation_with_equal_values(self):
        """Test creating fuzzy number where all three values are equal."""
        fuzzy = FuzzyTriangleNumber(lower_bound=10.0, peak=10.0, upper_bound=10.0)

        assert fuzzy.lower_bound == 10.0
        assert fuzzy.peak == 10.0
        assert fuzzy.upper_bound == 10.0

    def test_creation_lower_equals_peak(self):
        """Test creating fuzzy number where lower_bound equals peak."""
        fuzzy = FuzzyTriangleNumber(lower_bound=5.0, peak=5.0, upper_bound=10.0)

        assert fuzzy.lower_bound == 5.0
        assert fuzzy.peak == 5.0
        assert fuzzy.upper_bound == 10.0

    def test_creation_peak_equals_upper(self):
        """Test creating fuzzy number where peak equals upper_bound."""
        fuzzy = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=10.0)

        assert fuzzy.lower_bound == 5.0
        assert fuzzy.peak == 10.0
        assert fuzzy.upper_bound == 10.0


class TestFuzzyTriangleNumberValidation:
    """Test cases for input validation."""

    def test_peak_less_than_lower_raises_error(self):
        """Test that peak < lower_bound raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            FuzzyTriangleNumber(lower_bound=10.0, peak=5.0, upper_bound=15.0)

        assert "lower_bound <= peak <= upper_bound" in str(exc_info.value)

    def test_upper_less_than_peak_raises_error(self):
        """Test that upper_bound < peak raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            FuzzyTriangleNumber(lower_bound=5.0, peak=15.0, upper_bound=10.0)

        assert "lower_bound <= peak <= upper_bound" in str(exc_info.value)

    def test_upper_less_than_lower_raises_error(self):
        """Test that upper_bound < lower_bound raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            FuzzyTriangleNumber(lower_bound=15.0, peak=10.0, upper_bound=5.0)

        assert "lower_bound <= peak <= upper_bound" in str(exc_info.value)

    def test_all_values_inverted_raises_error(self):
        """Test that completely inverted values raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            FuzzyTriangleNumber(lower_bound=20.0, peak=10.0, upper_bound=5.0)

        assert "lower_bound <= peak <= upper_bound" in str(exc_info.value)


class TestFuzzyTriangleNumberCentroid:
    """Test cases for centroid calculation."""

    def test_centroid_calculation(self):
        """Test centroid calculation with normal values."""
        fuzzy = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)

        expected_centroid = (5.0 + 10.0 + 15.0) / 3.0
        assert fuzzy.get_centroid() == expected_centroid
        assert fuzzy.get_centroid() == 10.0

    def test_centroid_with_equal_values(self):
        """Test centroid when all values are equal."""
        fuzzy = FuzzyTriangleNumber(lower_bound=7.0, peak=7.0, upper_bound=7.0)

        assert fuzzy.get_centroid() == 7.0

    def test_centroid_with_decimals(self):
        """Test centroid calculation with decimal values."""
        fuzzy = FuzzyTriangleNumber(lower_bound=6.5, peak=8.3, upper_bound=11.2)

        expected_centroid = (6.5 + 8.3 + 11.2) / 3.0
        assert abs(fuzzy.get_centroid() - expected_centroid) < 1e-10

    def test_centroid_from_excel_example(self):
        """Test centroid with values from Excel reference."""
        # Project manager from Excel: best=15, lower=10, upper=15
        fuzzy = FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=15.0)

        expected_centroid = (10.0 + 15.0 + 15.0) / 3.0
        assert abs(fuzzy.get_centroid() - expected_centroid) < 1e-10
        assert abs(fuzzy.get_centroid() - 13.333333333333334) < 1e-10


class TestFuzzyTriangleNumberStringRepresentation:
    """Test cases for string representations."""

    def test_str_representation(self):
        """Test __str__ method."""
        fuzzy = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)

        assert str(fuzzy) == "(5.00, 10.00, 15.00)"

    def test_repr_representation(self):
        """Test __repr__ method."""
        fuzzy = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)

        repr_str = repr(fuzzy)
        assert "FuzzyTriangleNumber" in repr_str
        assert "lower=5.0" in repr_str
        assert "peak=10.0" in repr_str
        assert "upper=15.0" in repr_str

    def test_repr_can_recreate_object(self):
        """Test that repr contains enough information to understand the object."""
        fuzzy = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        repr_str = repr(fuzzy)

        # Should contain class name and all values
        assert "FuzzyTriangleNumber" in repr_str
        assert "5.0" in repr_str
        assert "10.0" in repr_str
        assert "15.0" in repr_str
