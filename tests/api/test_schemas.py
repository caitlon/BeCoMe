"""Unit tests for API request/response schemas."""

import math

import pytest
from pydantic import ValidationError

from api.schemas import ExpertInput


class TestExpertInputValidation:
    """Validation tests for ExpertInput schema."""

    def test_valid_input_accepted(self):
        """
        GIVEN valid fuzzy number values
        WHEN ExpertInput is created
        THEN no validation error is raised
        """
        # WHEN/THEN
        expert = ExpertInput(name="Test", lower=5.0, peak=10.0, upper=15.0)
        assert expert.lower == 5.0
        assert expert.peak == 10.0
        assert expert.upper == 15.0

    def test_nan_value_rejected(self):
        """
        GIVEN NaN value in fuzzy number
        WHEN ExpertInput is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="finite"):
            ExpertInput(name="Test", lower=5.0, peak=math.nan, upper=15.0)

    def test_positive_infinity_rejected(self):
        """
        GIVEN positive infinity value in fuzzy number
        WHEN ExpertInput is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="finite"):
            ExpertInput(name="Test", lower=5.0, peak=10.0, upper=math.inf)

    def test_negative_infinity_rejected(self):
        """
        GIVEN negative infinity value in fuzzy number
        WHEN ExpertInput is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="finite"):
            ExpertInput(name="Test", lower=-math.inf, peak=10.0, upper=15.0)
