"""
Integration tests for the complete data pipeline.

These tests verify the end-to-end flow:
txt file → parsing → BeCoMe calculation → results validation

This ensures that data files in examples/data/ can be successfully
loaded and processed through the entire pipeline.
"""

import pytest

from examples.utils import load_data_from_txt
from src.calculators.become_calculator import BeCoMeCalculator
from tests.reference import BUDGET_CASE, FLOODS_CASE, PENDLERS_CASE


class TestDataPipeline:
    """End-to-end tests for the complete data processing pipeline."""

    @pytest.mark.parametrize(
        "data_file,reference_case,case_name",
        [
            ("examples/data/budget_case.txt", BUDGET_CASE, "Budget"),
            ("examples/data/floods_case.txt", FLOODS_CASE, "Floods"),
            ("examples/data/pendlers_case.txt", PENDLERS_CASE, "Pendlers"),
        ],
    )
    def test_txt_to_result_pipeline(self, data_file: str, reference_case: dict, case_name: str):
        """Test complete pipeline: load txt → parse → calculate → validate."""
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
