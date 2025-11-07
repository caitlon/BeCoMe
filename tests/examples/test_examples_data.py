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


class TestDataLoadingErrorHandling:
    """Test error handling in data loading."""

    def test_file_not_found_raises_error(self, tmp_path):
        """Test that FileNotFoundError is raised for non-existent files."""
        # Arrange
        non_existent_file: str = str(tmp_path / "does_not_exist.txt")

        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            load_data_from_txt(non_existent_file)

        assert "Data file not found" in str(exc_info.value)
        assert non_existent_file in str(exc_info.value)

    def test_invalid_line_format_too_few_parts(self, tmp_path):
        """Test that ValueError is raised for lines with less than 4 parts."""
        # Arrange
        test_file = tmp_path / "invalid_format.txt"
        test_file.write_text(
            """CASE: Test
DESCRIPTION: Invalid format test
EXPERTS: 1

E1 | 10 | 20
""",
            encoding="utf-8",
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_data_from_txt(str(test_file))

        assert "Invalid line format" in str(exc_info.value)
        assert "expected 4 parts" in str(exc_info.value)

    def test_invalid_line_format_too_many_parts(self, tmp_path):
        """Test that ValueError is raised for lines with more than 4 parts."""
        # Arrange
        test_file = tmp_path / "invalid_format.txt"
        test_file.write_text(
            """CASE: Test
DESCRIPTION: Invalid format test
EXPERTS: 1

E1 | 10 | 20 | 30 | 40
""",
            encoding="utf-8",
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_data_from_txt(str(test_file))

        assert "Invalid line format" in str(exc_info.value)
        assert "expected 4 parts" in str(exc_info.value)

    def test_invalid_numeric_values_non_float_lower(self, tmp_path):
        """Test that ValueError is raised for non-numeric lower bound."""
        # Arrange
        test_file = tmp_path / "invalid_numbers.txt"
        test_file.write_text(
            """CASE: Test
DESCRIPTION: Invalid numbers test
EXPERTS: 1

E1 | abc | 20 | 30
""",
            encoding="utf-8",
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_data_from_txt(str(test_file))

        assert "Invalid numeric values" in str(exc_info.value)

    def test_invalid_numeric_values_non_float_peak(self, tmp_path):
        """Test that ValueError is raised for non-numeric peak."""
        # Arrange
        test_file = tmp_path / "invalid_numbers.txt"
        test_file.write_text(
            """CASE: Test
DESCRIPTION: Invalid numbers test
EXPERTS: 1

E1 | 10 | xyz | 30
""",
            encoding="utf-8",
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_data_from_txt(str(test_file))

        assert "Invalid numeric values" in str(exc_info.value)

    def test_invalid_numeric_values_non_float_upper(self, tmp_path):
        """Test that ValueError is raised for non-numeric upper bound."""
        # Arrange
        test_file = tmp_path / "invalid_numbers.txt"
        test_file.write_text(
            """CASE: Test
DESCRIPTION: Invalid numbers test
EXPERTS: 1

E1 | 10 | 20 | invalid
""",
            encoding="utf-8",
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_data_from_txt(str(test_file))

        assert "Invalid numeric values" in str(exc_info.value)

    def test_expert_count_mismatch_too_few(self, tmp_path):
        """Test that ValueError is raised when fewer experts than expected."""
        # Arrange
        test_file = tmp_path / "count_mismatch.txt"
        test_file.write_text(
            """CASE: Test
DESCRIPTION: Count mismatch test
EXPERTS: 3

E1 | 10 | 20 | 30
E2 | 15 | 25 | 35
""",
            encoding="utf-8",
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_data_from_txt(str(test_file))

        assert "Expected 3 experts but loaded 2" in str(exc_info.value)

    def test_expert_count_mismatch_too_many(self, tmp_path):
        """Test that ValueError is raised when more experts than expected."""
        # Arrange
        test_file = tmp_path / "count_mismatch.txt"
        test_file.write_text(
            """CASE: Test
DESCRIPTION: Count mismatch test
EXPERTS: 2

E1 | 10 | 20 | 30
E2 | 15 | 25 | 35
E3 | 20 | 30 | 40
""",
            encoding="utf-8",
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_data_from_txt(str(test_file))

        assert "Expected 2 experts but loaded 3" in str(exc_info.value)

    def test_empty_lines_and_comments_are_skipped(self, tmp_path):
        """Test that empty lines and comments don't affect parsing."""
        # Arrange
        test_file = tmp_path / "with_comments.txt"
        test_file.write_text(
            """CASE: Test
DESCRIPTION: Test with comments
EXPERTS: 2

# This is a comment
E1 | 10 | 20 | 30

# Another comment
E2 | 15 | 25 | 35

""",
            encoding="utf-8",
        )

        # Act
        opinions, metadata = load_data_from_txt(str(test_file))

        # Assert
        assert len(opinions) == 2
        assert metadata["case"] == "Test"

    def test_valid_file_with_no_expert_count_metadata(self, tmp_path):
        """Test that files without EXPERTS metadata are loaded without validation."""
        # Arrange
        test_file = tmp_path / "no_count.txt"
        test_file.write_text(
            """CASE: Test
DESCRIPTION: No expert count specified

E1 | 10 | 20 | 30
E2 | 15 | 25 | 35
""",
            encoding="utf-8",
        )

        # Act
        opinions, metadata = load_data_from_txt(str(test_file))

        # Assert
        assert len(opinions) == 2
        assert "num_experts" not in metadata
