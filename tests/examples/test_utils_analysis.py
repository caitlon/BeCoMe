"""
Unit tests for examples.utils.analysis module.

Tests the agreement level calculation function used to determine
expert consensus quality based on maximum error values.
"""

from examples.utils.analysis import calculate_agreement_level


class TestCalculateAgreementLevel:
    """Test cases for calculate_agreement_level function."""

    def test_good_agreement_below_threshold(self):
        """Test that max_error below 1.0 returns 'good'."""
        # Default thresholds: (1.0, 3.0)
        assert calculate_agreement_level(0.5) == "good"
        assert calculate_agreement_level(0.0) == "good"
        assert calculate_agreement_level(0.99) == "good"

    def test_good_agreement_at_boundary(self):
        """Test that max_error exactly at good threshold boundary."""
        # At exactly 1.0, should still be "good" (< 1.0 is false, so moderate)
        assert calculate_agreement_level(0.999) == "good"

    def test_moderate_agreement_in_range(self):
        """Test that max_error between thresholds returns 'moderate'."""
        # Between 1.0 and 3.0
        assert calculate_agreement_level(1.0) == "moderate"
        assert calculate_agreement_level(2.0) == "moderate"
        assert calculate_agreement_level(2.99) == "moderate"

    def test_low_agreement_above_threshold(self):
        """Test that max_error at or above 3.0 returns 'low'."""
        assert calculate_agreement_level(3.0) == "low"
        assert calculate_agreement_level(5.0) == "low"
        assert calculate_agreement_level(10.0) == "low"

    def test_custom_thresholds_good(self):
        """Test with custom thresholds for good agreement."""
        # Custom thresholds: (5.0, 10.0) - for Likert scale
        assert calculate_agreement_level(3.0, thresholds=(5.0, 10.0)) == "good"
        assert calculate_agreement_level(4.99, thresholds=(5.0, 10.0)) == "good"

    def test_custom_thresholds_moderate(self):
        """Test with custom thresholds for moderate agreement."""
        # Custom thresholds: (5.0, 10.0)
        assert calculate_agreement_level(5.0, thresholds=(5.0, 10.0)) == "moderate"
        assert calculate_agreement_level(7.5, thresholds=(5.0, 10.0)) == "moderate"
        assert calculate_agreement_level(9.99, thresholds=(5.0, 10.0)) == "moderate"

    def test_custom_thresholds_low(self):
        """Test with custom thresholds for low agreement."""
        # Custom thresholds: (5.0, 10.0)
        assert calculate_agreement_level(10.0, thresholds=(5.0, 10.0)) == "low"
        assert calculate_agreement_level(15.0, thresholds=(5.0, 10.0)) == "low"

    def test_edge_case_zero_error(self):
        """Test with zero error (perfect agreement)."""
        assert calculate_agreement_level(0.0) == "good"
        assert calculate_agreement_level(0.0, thresholds=(1.0, 3.0)) == "good"

    def test_edge_case_very_small_error(self):
        """Test with very small error values."""
        assert calculate_agreement_level(0.001) == "good"
        assert calculate_agreement_level(0.1) == "good"

    def test_edge_case_boundary_transitions(self):
        """Test exact boundary values between categories."""
        # With default thresholds (1.0, 3.0)
        assert calculate_agreement_level(0.999999) == "good"
        assert calculate_agreement_level(1.0) == "moderate"
        assert calculate_agreement_level(1.000001) == "moderate"
        assert calculate_agreement_level(2.999999) == "moderate"
        assert calculate_agreement_level(3.0) == "low"
        assert calculate_agreement_level(3.000001) == "low"

    def test_real_world_budget_case(self):
        """Test with real max_error from Budget case study."""
        # Budget case: max_error ≈ 0.71 → should be "good"
        assert calculate_agreement_level(0.71) == "good"

    def test_real_world_floods_case(self):
        """Test with real max_error from Floods case study."""
        # Floods case: max_error ≈ 5.97 → should be "low" with default thresholds
        assert calculate_agreement_level(5.97) == "low"

    def test_real_world_pendlers_case_likert(self):
        """Test with real max_error from Pendlers case (Likert scale)."""
        # Pendlers case uses different thresholds (5.0, 10.0)
        # Pendlers max_error ≈ 6.36 → should be "moderate"
        assert calculate_agreement_level(6.36, thresholds=(5.0, 10.0)) == "moderate"

    def test_tuple_unpacking_thresholds(self):
        """Test that thresholds tuple is properly unpacked."""
        good_threshold = 2.0
        moderate_threshold = 5.0
        thresholds = (good_threshold, moderate_threshold)

        assert calculate_agreement_level(1.5, thresholds=thresholds) == "good"
        assert calculate_agreement_level(3.5, thresholds=thresholds) == "moderate"
        assert calculate_agreement_level(6.0, thresholds=thresholds) == "low"

    def test_default_thresholds_values(self):
        """Test that default thresholds are (1.0, 3.0) as documented."""
        # This implicitly tests the default by not passing thresholds
        assert calculate_agreement_level(0.5) == "good"  # < 1.0
        assert calculate_agreement_level(2.0) == "moderate"  # between 1.0 and 3.0
        assert calculate_agreement_level(4.0) == "low"  # >= 3.0
