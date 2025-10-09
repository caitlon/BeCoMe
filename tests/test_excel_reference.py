"""
Integration tests for BeCoMe with Excel reference data.

These tests verify that our implementation produces results matching
the Excel reference implementation within acceptable tolerance.
"""

import pytest

from src.calculators.become_calculator import BeCoMeCalculator
from tests.data.excel_cases import BUDGET_CASE, PENDLERS_CASE


class TestExcelIntegration:
    """Integration tests comparing BeCoMe calculations with Excel reference data."""

    def test_budget_case(self):
        """Test BeCoMe with the Budget case from Excel."""
        # Arrange
        calculator = BeCoMeCalculator()
        expected = BUDGET_CASE["expected_result"]

        # Act
        result = calculator.calculate_compromise(BUDGET_CASE["opinions"])

        # Assert - Best compromise fuzzy number components
        assert (
            abs(result.best_compromise.lower_bound - expected["best_compromise_lower"]) < 0.001
        ), (
            f"Best compromise lower mismatch: got {result.best_compromise.lower_bound}, "
            f"expected {expected['best_compromise_lower']}"
        )
        assert abs(result.best_compromise.peak - expected["best_compromise_peak"]) < 0.001, (
            f"Best compromise peak mismatch: got {result.best_compromise.peak}, "
            f"expected {expected['best_compromise_peak']}"
        )
        assert (
            abs(result.best_compromise.upper_bound - expected["best_compromise_upper"]) < 0.001
        ), (
            f"Best compromise upper mismatch: got {result.best_compromise.upper_bound}, "
            f"expected {expected['best_compromise_upper']}"
        )

        # Check centroid matches Excel display value
        result_centroid = result.best_compromise.get_centroid()
        assert abs(result_centroid - expected["best_compromise_centroid"]) < 0.01, (
            f"Best compromise centroid mismatch: got {result_centroid}, "
            f"expected {expected['best_compromise_centroid']}"
        )

        # Arithmetic mean fuzzy number
        assert abs(result.arithmetic_mean.lower_bound - expected["mean_lower"]) < 0.001
        assert abs(result.arithmetic_mean.peak - expected["mean_peak"]) < 0.001
        assert abs(result.arithmetic_mean.upper_bound - expected["mean_upper"]) < 0.001

        # Median fuzzy number
        assert abs(result.median.lower_bound - expected["median_lower"]) < 0.001
        assert abs(result.median.peak - expected["median_peak"]) < 0.001
        assert abs(result.median.upper_bound - expected["median_upper"]) < 0.001

        # Max error (now a scalar, not fuzzy number)
        assert abs(result.max_error - expected["max_error"]) < 0.01, (
            f"Max error mismatch: got {result.max_error}, expected {expected['max_error']}"
        )

        # Expert count should match exactly
        assert result.num_experts == expected["num_experts"]

    def test_pendlers_case(self):
        """Test BeCoMe with the Pendlers case from Excel (Likert scale data)."""
        # Arrange
        calculator = BeCoMeCalculator()
        expected = PENDLERS_CASE["expected_result"]

        # Act
        result = calculator.calculate_compromise(PENDLERS_CASE["opinions"])

        # Assert
        # Best compromise peak should match with precision < 0.001
        assert abs(result.best_compromise.peak - expected["best_compromise_peak"]) < 0.001, (
            f"Best compromise peak mismatch: got {result.best_compromise.peak}, "
            f"expected {expected['best_compromise_peak']}"
        )

        # Max error is now a scalar (float), not fuzzy number
        assert abs(result.max_error - expected["max_error"]) < 0.01, (
            f"Max error mismatch: got {result.max_error}, expected {expected['max_error']}"
        )

        # Verify mean and median
        assert abs(result.arithmetic_mean.peak - expected["mean_peak"]) < 0.001, (
            f"Arithmetic mean peak mismatch: got {result.arithmetic_mean.peak}, "
            f"expected {expected['mean_peak']}"
        )

        assert abs(result.median.peak - expected["median_peak"]) < 0.001, (
            f"Median peak mismatch: got {result.median.peak}, expected {expected['median_peak']}"
        )

        # Verify median bounds for Likert (should be same as peak)
        assert abs(result.median.lower_bound - expected["median_lower"]) < 0.001, (
            f"Median lower bound mismatch: got {result.median.lower_bound}, "
            f"expected {expected['median_lower']}"
        )

        assert abs(result.median.upper_bound - expected["median_upper"]) < 0.001, (
            f"Median upper bound mismatch: got {result.median.upper_bound}, "
            f"expected {expected['median_upper']}"
        )

        # Check that number of experts matches
        assert result.num_experts == expected["num_experts"]

    @pytest.mark.parametrize(
        "case_name,case_data", [("BUDGET_CASE", BUDGET_CASE), ("PENDLERS_CASE", PENDLERS_CASE)]
    )
    def test_all_excel_cases(self, case_name, case_data):
        """Test all Excel cases with parametrized test."""
        # Arrange
        calculator = BeCoMeCalculator()
        expected = case_data["expected_result"]

        # Act
        result = calculator.calculate_compromise(case_data["opinions"])

        # Assert
        # Basic validation for all cases
        assert abs(result.best_compromise.peak - expected["best_compromise_peak"]) < 0.001, (
            f"{case_name} best compromise peak mismatch: got {result.best_compromise.peak}, "
            f"expected {expected['best_compromise_peak']}"
        )

        # Max error is now a scalar (float), not fuzzy number
        assert abs(result.max_error - expected["max_error"]) < 0.01, (
            f"{case_name} max error mismatch: got {result.max_error}, "
            f"expected {expected['max_error']}"
        )

        assert result.num_experts == expected["num_experts"], (
            f"{case_name} expert count mismatch: got {result.num_experts}, "
            f"expected {expected['num_experts']}"
        )
