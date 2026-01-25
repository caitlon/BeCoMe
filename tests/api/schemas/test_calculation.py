"""Tests for calculation schemas."""

import pytest
from pydantic import ValidationError

from api.schemas.calculation import ExpertInput, FuzzyNumberOutput
from src.models.fuzzy_number import FuzzyTriangleNumber


class TestExpertInputConstraints:
    """Tests for ExpertInput fuzzy constraints validation."""

    def test_lower_greater_than_peak_rejected(self):
        """
        GIVEN lower > peak
        WHEN ExpertInput is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="lower <= peak <= upper"):
            ExpertInput(name="Expert", lower=15.0, peak=10.0, upper=20.0)

    def test_peak_greater_than_upper_rejected(self):
        """
        GIVEN peak > upper
        WHEN ExpertInput is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="lower <= peak <= upper"):
            ExpertInput(name="Expert", lower=5.0, peak=25.0, upper=20.0)

    def test_equal_values_accepted(self):
        """
        GIVEN lower == peak == upper
        WHEN ExpertInput is created
        THEN no error is raised (degenerate case is valid)
        """
        # WHEN
        expert = ExpertInput(name="Expert", lower=10.0, peak=10.0, upper=10.0)

        # THEN
        assert expert.lower == 10.0
        assert expert.peak == 10.0
        assert expert.upper == 10.0


class TestFuzzyNumberOutputFromDomain:
    """Tests for FuzzyNumberOutput.from_domain method."""

    def test_creates_output_from_domain(self):
        """
        GIVEN a FuzzyTriangleNumber domain object
        WHEN from_domain is called
        THEN FuzzyNumberOutput is created with correct values
        """
        # GIVEN
        fuzzy = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)

        # WHEN
        output = FuzzyNumberOutput.from_domain(fuzzy)

        # THEN
        assert output.lower == 5.0
        assert output.peak == 10.0
        assert output.upper == 15.0
        assert output.centroid == fuzzy.centroid

    def test_centroid_calculated_correctly(self):
        """
        GIVEN a FuzzyTriangleNumber
        WHEN from_domain is called
        THEN centroid matches (lower + peak + upper) / 3
        """
        # GIVEN
        fuzzy = FuzzyTriangleNumber(lower_bound=0.0, peak=6.0, upper_bound=12.0)
        expected_centroid = (0.0 + 6.0 + 12.0) / 3

        # WHEN
        output = FuzzyNumberOutput.from_domain(fuzzy)

        # THEN
        assert output.centroid == expected_centroid
