"""
Unit tests for examples.utils.analysis module.

Tests the agreement level calculation function used to determine
expert consensus quality based on maximum error values.
"""

import pytest

from examples.utils.analysis import calculate_agreement_level


class TestCalculateAgreementLevel:
    """Test cases for calculate_agreement_level function."""

    @pytest.mark.parametrize(
        "max_error,expected_level",
        [
            # Good agreement (< 1.0)
            (0.0, "good"),
            (0.5, "good"),
            (0.99, "good"),
            (0.999, "good"),
            # Moderate agreement (1.0 <= x < 3.0)
            (1.0, "moderate"),
            (2.0, "moderate"),
            (2.99, "moderate"),
            # Low agreement (>= 3.0)
            (3.0, "low"),
            (5.0, "low"),
            (10.0, "low"),
        ],
    )
    def test_agreement_levels_with_default_thresholds(
        self, max_error: float, expected_level: str
    ):
        """Test agreement level calculation with default thresholds (1.0, 3.0)."""
        assert calculate_agreement_level(max_error) == expected_level

    @pytest.mark.parametrize(
        "max_error,expected_level",
        [
            # Good agreement (< 5.0)
            (0.0, "good"),
            (3.0, "good"),
            (4.99, "good"),
            # Moderate agreement (5.0 <= x < 10.0)
            (5.0, "moderate"),
            (7.5, "moderate"),
            (9.99, "moderate"),
            # Low agreement (>= 10.0)
            (10.0, "low"),
            (15.0, "low"),
        ],
    )
    def test_agreement_levels_with_custom_thresholds(
        self, max_error: float, expected_level: str
    ):
        """Test agreement level calculation with custom thresholds (5.0, 10.0) for Likert scale."""
        assert calculate_agreement_level(max_error, thresholds=(5.0, 10.0)) == expected_level

    def test_boundary_transitions(self):
        """Test exact boundary values between categories."""
        # Test transitions between good/moderate/low
        assert calculate_agreement_level(0.999999) == "good"
        assert calculate_agreement_level(1.0) == "moderate"
        assert calculate_agreement_level(1.000001) == "moderate"
        assert calculate_agreement_level(2.999999) == "moderate"
        assert calculate_agreement_level(3.0) == "low"
        assert calculate_agreement_level(3.000001) == "low"
