"""Unit tests for examples.utils.analysis module."""

import pytest

from examples.utils.analysis import calculate_agreement_level


class TestCalculateAgreementLevel:
    """Test cases for calculate_agreement_level function."""

    @pytest.mark.parametrize(
        "max_error,expected_level",
        [
            (0.0, "good"),
            (0.5, "good"),
            (0.99, "good"),
            (0.999, "good"),
            (1.0, "moderate"),
            (2.0, "moderate"),
            (2.99, "moderate"),
            (3.0, "low"),
            (5.0, "low"),
            (10.0, "low"),
        ],
    )
    def test_agreement_levels_with_default_thresholds(
        self, max_error: float, expected_level: str
    ) -> None:
        """Test agreement level calculation with default thresholds."""
        # WHEN
        result = calculate_agreement_level(max_error)

        # THEN
        assert result == expected_level

    @pytest.mark.parametrize(
        "max_error,expected_level",
        [
            (0.0, "good"),
            (3.0, "good"),
            (4.99, "good"),
            (5.0, "moderate"),
            (7.5, "moderate"),
            (9.99, "moderate"),
            (10.0, "low"),
            (15.0, "low"),
        ],
    )
    def test_agreement_levels_with_custom_thresholds(
        self, max_error: float, expected_level: str
    ) -> None:
        """Test agreement level calculation with custom thresholds."""
        # WHEN
        result = calculate_agreement_level(max_error, thresholds=(5.0, 10.0))

        # THEN
        assert result == expected_level

    def test_boundary_transitions(self) -> None:
        """Test exact boundary values between categories."""
        # WHEN / THEN
        assert calculate_agreement_level(0.999999) == "good"
        assert calculate_agreement_level(1.0) == "moderate"
        assert calculate_agreement_level(1.000001) == "moderate"
        assert calculate_agreement_level(2.999999) == "moderate"
        assert calculate_agreement_level(3.0) == "low"
        assert calculate_agreement_level(3.000001) == "low"
