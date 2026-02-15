"""Tests for shared validators."""

import math

import pytest

from api.schemas.validators import validate_fuzzy_constraints


class TestValidateFuzzyConstraints:
    """Tests for validate_fuzzy_constraints function."""

    def test_valid_values_pass(self):
        """
        GIVEN valid fuzzy number values (lower <= peak <= upper)
        WHEN validate_fuzzy_constraints is called
        THEN no error is raised
        """
        # WHEN/THEN - no exception
        validate_fuzzy_constraints(5.0, 10.0, 15.0)

    def test_equal_values_pass(self):
        """
        GIVEN all equal values (degenerate case)
        WHEN validate_fuzzy_constraints is called
        THEN no error is raised
        """
        # WHEN/THEN - no exception
        validate_fuzzy_constraints(10.0, 10.0, 10.0)

    def test_nan_value_raises_error(self):
        """
        GIVEN NaN in values
        WHEN validate_fuzzy_constraints is called
        THEN ValueError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValueError, match="finite"):
            validate_fuzzy_constraints(5.0, math.nan, 15.0)

    def test_positive_infinity_raises_error(self):
        """
        GIVEN positive infinity in values
        WHEN validate_fuzzy_constraints is called
        THEN ValueError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValueError, match="finite"):
            validate_fuzzy_constraints(5.0, 10.0, math.inf)

    def test_negative_infinity_raises_error(self):
        """
        GIVEN negative infinity in values
        WHEN validate_fuzzy_constraints is called
        THEN ValueError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValueError, match="finite"):
            validate_fuzzy_constraints(-math.inf, 10.0, 15.0)

    def test_lower_greater_than_peak_raises_error(self):
        """
        GIVEN lower > peak
        WHEN validate_fuzzy_constraints is called
        THEN ValueError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValueError, match="lower <= peak <= upper"):
            validate_fuzzy_constraints(15.0, 10.0, 20.0)

    def test_peak_greater_than_upper_raises_error(self):
        """
        GIVEN peak > upper
        WHEN validate_fuzzy_constraints is called
        THEN ValueError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValueError, match="lower <= peak <= upper"):
            validate_fuzzy_constraints(5.0, 25.0, 20.0)
