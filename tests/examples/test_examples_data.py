"""
Tests for examples data loading and analysis.

These tests verify that the text data files in examples/data/ load correctly
and produce the same results as the reference test data.
"""

from pathlib import Path

import pytest

from examples.utils import load_data_from_txt
from src.calculators.become_calculator import BeCoMeCalculator
from tests.reference import BUDGET_CASE, FLOODS_CASE, PENDLERS_CASE


class TestExamplesDataLoading:
    """Test that example data files load correctly and match reference data."""

    def test_budget_case_loads_correctly(self):
        """Test that budget_case.txt loads and produces correct results."""
        # Arrange
        data_file = Path("examples/data/budget_case.txt")
        expected = BUDGET_CASE["expected_result"]

        # Act - Load data from text file
        opinions, metadata = load_data_from_txt(str(data_file))

        # Assert - Metadata is correct
        assert metadata["case"] == "Budget"
        assert int(metadata["num_experts"]) == 22
        assert len(opinions) == 22

        # Calculate and verify results match reference
        calculator = BeCoMeCalculator()
        result = calculator.calculate_compromise(opinions)

        # Best compromise should match
        assert abs(result.best_compromise.lower_bound - expected["best_compromise_lower"]) < 0.001
        assert abs(result.best_compromise.peak - expected["best_compromise_peak"]) < 0.001
        assert abs(result.best_compromise.upper_bound - expected["best_compromise_upper"]) < 0.001

        # Max error should match
        assert abs(result.max_error - expected["max_error"]) < 0.01

        # Number of experts should match
        assert result.num_experts == expected["num_experts"]
        assert result.is_even is True

    def test_floods_case_loads_correctly(self):
        """Test that floods_case.txt loads and produces correct results."""
        # Arrange
        data_file = Path("examples/data/floods_case.txt")
        expected = FLOODS_CASE["expected_result"]

        # Act - Load data from text file
        opinions, metadata = load_data_from_txt(str(data_file))

        # Assert - Metadata is correct
        assert metadata["case"] == "Floods"
        assert int(metadata["num_experts"]) == 13
        assert len(opinions) == 13

        # Calculate and verify results match reference
        calculator = BeCoMeCalculator()
        result = calculator.calculate_compromise(opinions)

        # Best compromise should match
        assert abs(result.best_compromise.lower_bound - expected["best_compromise_lower"]) < 0.001
        assert abs(result.best_compromise.peak - expected["best_compromise_peak"]) < 0.001
        assert abs(result.best_compromise.upper_bound - expected["best_compromise_upper"]) < 0.001

        # Max error should match
        assert abs(result.max_error - expected["max_error"]) < 0.01

        # Number of experts should match
        assert result.num_experts == expected["num_experts"]
        assert result.is_even is False  # Odd number of experts

    def test_pendlers_case_loads_correctly(self):
        """Test that pendlers_case.txt loads and produces correct results."""
        # Arrange
        data_file = Path("examples/data/pendlers_case.txt")
        expected = PENDLERS_CASE["expected_result"]

        # Act - Load data from text file
        opinions, metadata = load_data_from_txt(str(data_file))

        # Assert - Metadata is correct
        assert metadata["case"] == "Pendlers"
        assert int(metadata["num_experts"]) == 22
        assert len(opinions) == 22

        # Calculate and verify results match reference
        calculator = BeCoMeCalculator()
        result = calculator.calculate_compromise(opinions)

        # Best compromise should match
        assert abs(result.best_compromise.peak - expected["best_compromise_peak"]) < 0.001

        # Max error should match
        assert abs(result.max_error - expected["max_error"]) < 0.01

        # Mean and median should match
        assert abs(result.arithmetic_mean.peak - expected["mean_peak"]) < 0.001
        assert abs(result.median.peak - expected["median_peak"]) < 0.001

        # Number of experts should match
        assert result.num_experts == expected["num_experts"]
        assert result.is_even is True

    @pytest.mark.parametrize(
        "data_file,reference_case,case_name",
        [
            ("examples/data/budget_case.txt", BUDGET_CASE, "Budget"),
            ("examples/data/floods_case.txt", FLOODS_CASE, "Floods"),
            ("examples/data/pendlers_case.txt", PENDLERS_CASE, "Pendlers"),
        ],
    )
    def test_all_example_cases(self, data_file, reference_case, case_name):
        """Parametrized test for all example data files."""
        # Arrange
        expected = reference_case["expected_result"]

        # Act - Load data from text file
        opinions, metadata = load_data_from_txt(data_file)

        # Assert - Metadata matches
        assert metadata["case"] == case_name
        assert len(opinions) == expected["num_experts"]

        # Calculate and verify results
        calculator = BeCoMeCalculator()
        result = calculator.calculate_compromise(opinions)

        # Best compromise peak should match
        assert abs(result.best_compromise.peak - expected["best_compromise_peak"]) < 0.001, (
            f"{case_name} best compromise peak mismatch: got {result.best_compromise.peak}, "
            f"expected {expected['best_compromise_peak']}"
        )

        # Max error should match
        assert abs(result.max_error - expected["max_error"]) < 0.01, (
            f"{case_name} max error mismatch: got {result.max_error}, "
            f"expected {expected['max_error']}"
        )

        # Number of experts should match
        assert result.num_experts == expected["num_experts"], (
            f"{case_name} expert count mismatch: got {result.num_experts}, "
            f"expected {expected['num_experts']}"
        )


class TestExamplesDataFormat:
    """Test the text file format parsing."""

    def test_metadata_parsing(self):
        """Test that metadata is parsed correctly from text files."""
        # Act
        _, metadata = load_data_from_txt("examples/data/budget_case.txt")

        # Assert
        assert "case" in metadata
        assert "description" in metadata
        assert "num_experts" in metadata
        assert metadata["case"] == "Budget"
        assert "COVID-19" in metadata["description"]

    def test_expert_opinion_parsing(self):
        """Test that expert opinions are parsed correctly."""
        # Act
        opinions, _ = load_data_from_txt("examples/data/budget_case.txt")

        # Assert - First expert should be Chairman
        assert opinions[0].expert_id == "Chairman"
        assert opinions[0].opinion.lower_bound == 40.0
        assert opinions[0].opinion.peak == 70.0
        assert opinions[0].opinion.upper_bound == 90.0

    def test_likert_scale_parsing(self):
        """Test that Likert scale data (crisp values) is parsed correctly."""
        # Act
        opinions, _ = load_data_from_txt("examples/data/pendlers_case.txt")

        # Assert - For Likert scale, lower = peak = upper
        for opinion in opinions:
            assert opinion.opinion.lower_bound == opinion.opinion.peak
            assert opinion.opinion.peak == opinion.opinion.upper_bound

    def test_expert_count_validation(self):
        """Test that the loader validates expert count."""
        # Act
        opinions, metadata = load_data_from_txt("examples/data/floods_case.txt")

        # Assert
        expected_count = int(metadata["num_experts"])
        actual_count = len(opinions)
        assert actual_count == expected_count == 13
