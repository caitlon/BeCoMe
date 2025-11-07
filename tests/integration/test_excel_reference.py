"""
Integration tests for BeCoMe with Excel reference data.

These tests verify that our implementation produces results matching
the Excel reference implementation within acceptable tolerance.
"""

import pytest

from examples.utils import load_data_from_txt
from src.calculators.become_calculator import BeCoMeCalculator
from tests.reference import BUDGET_CASE, FLOODS_CASE, PENDLERS_CASE


class TestExcelIntegration:
    """Integration tests comparing BeCoMe calculations with Excel reference data."""

    @pytest.mark.parametrize(
        "case_name,case_data",
        [
            ("BUDGET", BUDGET_CASE),
            ("FLOODS", FLOODS_CASE),
            ("PENDLERS", PENDLERS_CASE),
        ],
    )
    def test_excel_reference_cases(self, case_name: str, case_data: dict):
        """Test all Excel reference cases with full validation."""
        # Arrange
        calculator = BeCoMeCalculator()
        expected = case_data["expected_result"]

        # Act
        result = calculator.calculate_compromise(case_data["opinions"])

        # Assert - Best compromise peak (always present)
        assert abs(result.best_compromise.peak - expected["best_compromise_peak"]) < 0.001, (
            f"{case_name}: Best compromise peak mismatch: "
            f"got {result.best_compromise.peak}, "
            f"expected {expected['best_compromise_peak']}"
        )

        # Assert - Best compromise bounds (if present in expected)
        if "best_compromise_lower" in expected:
            assert (
                abs(result.best_compromise.lower_bound - expected["best_compromise_lower"]) < 0.001
            ), (
                f"{case_name}: Best compromise lower mismatch: "
                f"got {result.best_compromise.lower_bound}, "
                f"expected {expected['best_compromise_lower']}"
            )

        if "best_compromise_upper" in expected:
            assert (
                abs(result.best_compromise.upper_bound - expected["best_compromise_upper"]) < 0.001
            ), (
                f"{case_name}: Best compromise upper mismatch: "
                f"got {result.best_compromise.upper_bound}, "
                f"expected {expected['best_compromise_upper']}"
            )

        # Assert - Best compromise centroid (if present)
        if "best_compromise_centroid" in expected:
            result_centroid = result.best_compromise.centroid
            assert abs(result_centroid - expected["best_compromise_centroid"]) < 0.01, (
                f"{case_name}: Best compromise centroid mismatch: "
                f"got {result_centroid}, "
                f"expected {expected['best_compromise_centroid']}"
            )

        # Assert - Arithmetic mean peak (always present)
        assert abs(result.arithmetic_mean.peak - expected["mean_peak"]) < 0.001, (
            f"{case_name}: Mean peak mismatch"
        )

        # Assert - Arithmetic mean bounds (if present)
        if "mean_lower" in expected:
            assert abs(result.arithmetic_mean.lower_bound - expected["mean_lower"]) < 0.001, (
                f"{case_name}: Mean lower bound mismatch"
            )

        if "mean_upper" in expected:
            assert abs(result.arithmetic_mean.upper_bound - expected["mean_upper"]) < 0.001, (
                f"{case_name}: Mean upper bound mismatch"
            )

        # Assert - Median fuzzy number
        assert abs(result.median.lower_bound - expected["median_lower"]) < 0.001, (
            f"{case_name}: Median lower bound mismatch"
        )
        assert abs(result.median.peak - expected["median_peak"]) < 0.001, (
            f"{case_name}: Median peak mismatch"
        )
        assert abs(result.median.upper_bound - expected["median_upper"]) < 0.001, (
            f"{case_name}: Median upper bound mismatch"
        )

        # Assert - Max error (scalar)
        assert abs(result.max_error - expected["max_error"]) < 0.01, (
            f"{case_name}: Max error mismatch: "
            f"got {result.max_error}, "
            f"expected {expected['max_error']}"
        )

        # Assert - Expert count
        assert result.num_experts == expected["num_experts"], (
            f"{case_name}: Expert count mismatch: "
            f"got {result.num_experts}, "
            f"expected {expected['num_experts']}"
        )

        # Assert - Even/odd validation for specific cases
        if case_name == "FLOODS":
            assert result.is_even is False, f"{case_name}: Should be odd (13 experts)"
        elif case_name in ["BUDGET", "PENDLERS"]:
            assert result.is_even is True, f"{case_name}: Should be even (22 experts)"

    @pytest.mark.parametrize(
        "data_file,reference_case,case_name",
        [
            ("examples/data/budget_case.txt", BUDGET_CASE, "Budget"),
            ("examples/data/floods_case.txt", FLOODS_CASE, "Floods"),
            ("examples/data/pendlers_case.txt", PENDLERS_CASE, "Pendlers"),
        ],
    )
    def test_txt_to_result_pipeline(self, data_file: str, reference_case: dict, case_name: str):
        """Test complete pipeline: load txt → parse → calculate → validate.

        This test verifies the end-to-end flow from text files to results,
        ensuring that data files in examples/data/ can be successfully
        loaded and processed through the entire pipeline.
        """
        # Arrange
        expected = reference_case["expected_result"]

        # Act - Load data from text file
        opinions, metadata = load_data_from_txt(data_file)

        # Assert - Parsing worked correctly
        assert metadata["case"] == case_name, f"Case name mismatch in {data_file}"
        assert len(opinions) == expected["num_experts"], (
            f"Expert count mismatch in {data_file}: "
            f"got {len(opinions)}, expected {expected['num_experts']}"
        )

        # Act - Calculate results
        calculator = BeCoMeCalculator()
        result = calculator.calculate_compromise(opinions)

        # Assert - Results match reference data
        assert abs(result.best_compromise.peak - expected["best_compromise_peak"]) < 0.001, (
            f"{case_name}: Best compromise peak mismatch after full pipeline: "
            f"got {result.best_compromise.peak}, "
            f"expected {expected['best_compromise_peak']}"
        )

        assert abs(result.max_error - expected["max_error"]) < 0.01, (
            f"{case_name}: Max error mismatch after full pipeline: "
            f"got {result.max_error}, "
            f"expected {expected['max_error']}"
        )

        assert result.num_experts == expected["num_experts"], (
            f"{case_name}: Expert count mismatch after full pipeline"
        )
