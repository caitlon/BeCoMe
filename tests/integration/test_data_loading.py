"""Tests for examples data loading and analysis."""

from typing import Any

import pytest

from examples.utils import load_data_from_txt
from src.calculators.become_calculator import BeCoMeCalculator
from tests.reference import BUDGET_CASE, FLOODS_CASE, PENDLERS_CASE


class TestExamplesDataLoading:
    """Test that example data files load correctly."""

    @pytest.mark.parametrize(
        "data_file,reference_case,case_name",
        [
            ("examples/data/budget_case.txt", BUDGET_CASE, "Budget"),
            ("examples/data/floods_case.txt", FLOODS_CASE, "Floods"),
            ("examples/data/pendlers_case.txt", PENDLERS_CASE, "Pendlers"),
        ],
    )
    def test_file_loading(
        self, data_file: str, reference_case: dict[str, Any], case_name: str
    ) -> None:
        """Test loading data from example text files."""
        # GIVEN
        expected = reference_case["expected_result"]

        # WHEN
        opinions, metadata = load_data_from_txt(data_file)

        # THEN
        assert metadata["case"] == case_name, f"{case_name} case name mismatch in metadata"
        assert len(opinions) == expected["num_experts"], (
            f"{case_name} expert count mismatch: got {len(opinions)}, "
            f"expected {expected['num_experts']}"
        )

    @pytest.mark.parametrize(
        "data_file,reference_case,case_name",
        [
            ("examples/data/budget_case.txt", BUDGET_CASE, "Budget"),
            ("examples/data/floods_case.txt", FLOODS_CASE, "Floods"),
            ("examples/data/pendlers_case.txt", PENDLERS_CASE, "Pendlers"),
        ],
    )
    def test_calculation_with_loaded_data(
        self,
        data_file: str,
        reference_case: dict[str, Any],
        case_name: str,
        calculator: BeCoMeCalculator,
    ) -> None:
        """Test BeCoMe calculations with data loaded from example files."""
        # GIVEN
        expected = reference_case["expected_result"]
        opinions, _ = load_data_from_txt(data_file)

        # WHEN
        result = calculator.calculate_compromise(opinions)

        # THEN
        assert abs(result.best_compromise.peak - expected["best_compromise_peak"]) < 0.001, (
            f"{case_name} best compromise peak mismatch: got {result.best_compromise.peak}, "
            f"expected {expected['best_compromise_peak']}"
        )
        assert abs(result.max_error - expected["max_error"]) < 0.01, (
            f"{case_name} max error mismatch: got {result.max_error}, "
            f"expected {expected['max_error']}"
        )
        assert result.num_experts == expected["num_experts"], (
            f"{case_name} expert count mismatch: got {result.num_experts}, "
            f"expected {expected['num_experts']}"
        )


class TestExamplesDataFormat:
    """Test the text file format parsing."""

    def test_metadata_parsing(self, budget_case_file: str) -> None:
        """Test that metadata is parsed correctly from text files."""
        # WHEN
        _, metadata = load_data_from_txt(budget_case_file)

        # THEN
        assert "case" in metadata
        assert "description" in metadata
        assert "num_experts" in metadata
        assert metadata["case"] == "Budget"
        assert "COVID-19" in metadata["description"]

    def test_expert_opinion_parsing(self, budget_case_file: str) -> None:
        """Test that expert opinions are parsed correctly."""
        # WHEN
        opinions, _ = load_data_from_txt(budget_case_file)

        # THEN
        assert opinions[0].expert_id == "Chairman"
        assert opinions[0].opinion.lower_bound == 40.0
        assert opinions[0].opinion.peak == 70.0
        assert opinions[0].opinion.upper_bound == 90.0

    def test_likert_scale_parsing(self, pendlers_case_file: str) -> None:
        """Test that Likert scale data (crisp values) is parsed correctly."""
        # WHEN
        opinions, _ = load_data_from_txt(pendlers_case_file)

        # THEN
        for opinion in opinions:
            assert opinion.opinion.lower_bound == opinion.opinion.peak
            assert opinion.opinion.peak == opinion.opinion.upper_bound

    def test_expert_count_validation(self, floods_case_file: str) -> None:
        """Test that the loader validates expert count against metadata."""
        # WHEN
        opinions, metadata = load_data_from_txt(floods_case_file)

        # THEN
        expected_count = int(metadata["num_experts"])
        actual_count = len(opinions)
        assert actual_count == expected_count == 13


class TestDataLoadingErrorHandling:
    """Test error handling in data loading."""

    def test_file_not_found_raises_error(self, tmp_path) -> None:
        """Test that FileNotFoundError is raised for non-existent files."""
        # GIVEN
        non_existent_file: str = str(tmp_path / "does_not_exist.txt")

        # WHEN / THEN
        with pytest.raises(FileNotFoundError) as exc_info:
            load_data_from_txt(non_existent_file)

        assert "Data file not found" in str(exc_info.value)
        assert non_existent_file in str(exc_info.value)

    @pytest.mark.parametrize(
        "data_line,expected_error",
        [
            ("E1 | 10 | 20", "Invalid line format"),  # Too few parts
            ("E1 | 10 | 20 | 30 | 40", "Invalid line format"),  # Too many parts
        ],
    )
    def test_invalid_line_format(self, tmp_path, data_line: str, expected_error: str) -> None:
        """Test that ValueError is raised for invalid line formats."""
        # GIVEN
        test_file = tmp_path / "invalid_format.txt"
        test_file.write_text(
            f"""CASE: Test
            DESCRIPTION: Invalid format test
            EXPERTS: 1

            {data_line}
            """,
            encoding="utf-8",
        )

        # WHEN / THEN
        with pytest.raises(ValueError) as exc_info:
            load_data_from_txt(str(test_file))

        assert expected_error in str(exc_info.value)
        assert "expected 4 parts" in str(exc_info.value)

    @pytest.mark.parametrize(
        "data_line",
        [
            "E1 | abc | 20 | 30",  # Invalid lower bound
            "E1 | 10 | xyz | 30",  # Invalid peak
            "E1 | 10 | 20 | invalid",  # Invalid upper bound
        ],
    )
    def test_invalid_numeric_values(self, tmp_path, data_line: str) -> None:
        """Test that ValueError is raised for non-numeric values."""
        # GIVEN
        test_file = tmp_path / "invalid_numbers.txt"
        test_file.write_text(
            f"""CASE: Test
            DESCRIPTION: Invalid numbers test
            EXPERTS: 1

            {data_line}
            """,
            encoding="utf-8",
        )

        # WHEN / THEN
        with pytest.raises(ValueError) as exc_info:
            load_data_from_txt(str(test_file))

        assert "Invalid numeric values" in str(exc_info.value)

    @pytest.mark.parametrize(
        "expected_count,data_lines,expected_message",
        [
            (3, "E1 | 10 | 20 | 30\nE2 | 15 | 25 | 35", "Expected 3 experts but loaded 2"),
            (
                2,
                "E1 | 10 | 20 | 30\nE2 | 15 | 25 | 35\nE3 | 20 | 30 | 40",
                "Expected 2 experts but loaded 3",
            ),
        ],
    )
    def test_expert_count_mismatch(
        self, tmp_path, expected_count: int, data_lines: str, expected_message: str
    ) -> None:
        """Test that ValueError is raised when expert count doesn't match metadata."""
        # GIVEN
        test_file = tmp_path / "count_mismatch.txt"
        test_file.write_text(
            f"""CASE: Test
            DESCRIPTION: Count mismatch test
            EXPERTS: {expected_count}

            {data_lines}
            """,
            encoding="utf-8",
        )

        # WHEN / THEN
        with pytest.raises(ValueError) as exc_info:
            load_data_from_txt(str(test_file))

        assert expected_message in str(exc_info.value)

    def test_empty_lines_and_comments_are_skipped(self, tmp_path) -> None:
        """Test that empty lines and comments don't affect parsing."""
        # GIVEN
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

        # WHEN
        opinions, metadata = load_data_from_txt(str(test_file))

        # THEN
        assert len(opinions) == 2
        assert metadata["case"] == "Test"

    def test_valid_file_with_no_expert_count_metadata(self, tmp_path) -> None:
        """Test that files without EXPERTS metadata are loaded without validation."""
        # GIVEN
        test_file = tmp_path / "no_count.txt"
        test_file.write_text(
            """CASE: Test
            DESCRIPTION: No expert count specified

            E1 | 10 | 20 | 30
            E2 | 15 | 25 | 35
            """,
            encoding="utf-8",
        )

        # WHEN
        opinions, metadata = load_data_from_txt(str(test_file))

        # THEN
        assert len(opinions) == 2
        assert "num_experts" not in metadata
