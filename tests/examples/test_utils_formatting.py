"""
Unit tests for examples.utils.formatting module.

Tests the console output formatting functions used to display
case study information and results in a structured format.
"""

from examples.utils.formatting import (
    display_case_header,
    display_centroid,
    print_header,
    print_section,
)
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


class TestPrintHeader:
    """Test cases for print_header function."""

    def test_print_header_default_width(self, capsys):
        """Test header printing with default width of 60."""
        print_header("Test Title")
        captured = capsys.readouterr()

        lines: list[str] = captured.out.strip().split("\n")

        assert len(lines) == 3
        assert lines[0] == "=" * 60
        assert "Test Title" in lines[1]
        assert lines[1] == "Test Title".center(60)
        assert lines[2] == "=" * 60

    def test_print_header_custom_width(self, capsys):
        """Test header printing with custom width."""
        print_header("Short", width=40)
        captured = capsys.readouterr()

        lines: list[str] = captured.out.strip().split("\n")

        assert len(lines) == 3
        assert lines[0] == "=" * 40
        assert lines[1] == "Short".center(40)
        assert lines[2] == "=" * 40

    def test_print_header_long_title(self, capsys):
        """Test header with a longer title."""
        title: str = "BUDGET CASE - DETAILED ANALYSIS"
        print_header(title, width=70)
        captured = capsys.readouterr()

        lines: list[str] = captured.out.strip().split("\n")

        assert len(lines) == 3
        assert lines[0] == "=" * 70
        assert title in lines[1]
        assert lines[2] == "=" * 70

    def test_print_header_starts_with_newline(self, capsys):
        """Test that header starts with a newline for spacing."""
        print_header("Test")
        captured = capsys.readouterr()

        assert captured.out.startswith("\n")


class TestPrintSection:
    """Test cases for print_section function."""

    def test_print_section_default_width(self, capsys):
        """Test section printing with default width of 60."""
        print_section("Section Title")
        captured = capsys.readouterr()

        output: str = captured.out.strip()

        assert "Section Title" in output
        assert "-" in output
        assert " Section Title " in output

    def test_print_section_custom_width(self, capsys):
        """Test section printing with custom width."""
        print_section("Step 1", width=40)
        captured = capsys.readouterr()

        output: str = captured.out.strip()

        assert "Step 1" in output
        assert "-" in output

    def test_print_section_padding_calculation(self, capsys):
        """Test that section padding is calculated correctly."""
        title: str = "Test"
        width: int = 60
        print_section(title, width=width)
        captured = capsys.readouterr()

        output: str = captured.out.strip()

        # Verify the format: "--- Title ---"
        assert f" {title} " in output
        # The total length should approximately match width
        # (padding - title - 2) // 2 on each side

    def test_print_section_starts_with_newline(self, capsys):
        """Test that section starts with a newline for spacing."""
        print_section("Test")
        captured = capsys.readouterr()

        assert captured.out.startswith("\n")


class TestDisplayCaseHeader:
    """Test cases for display_case_header function."""

    def test_display_case_header_odd_experts(self, capsys):
        """Test case header display with odd number of experts."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(1.0, 2.0, 3.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(2.0, 3.0, 4.0)),
            ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(3.0, 4.0, 5.0)),
        ]
        metadata: dict[str, str] = {
            "case": "Budget",
            "description": "Test case for budget",
        }

        display_case_header("BUDGET CASE", opinions, metadata)
        captured = capsys.readouterr()

        output: str = captured.out

        assert "BUDGET CASE - DETAILED ANALYSIS" in output
        assert "Case: Budget" in output
        assert "Description: Test case for budget" in output
        assert "Number of experts: 3" in output
        assert "(odd)" in output

    def test_display_case_header_even_experts(self, capsys):
        """Test case header display with even number of experts."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(1.0, 2.0, 3.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(2.0, 3.0, 4.0)),
            ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(3.0, 4.0, 5.0)),
            ExpertOpinion(expert_id="E4", opinion=FuzzyTriangleNumber(4.0, 5.0, 6.0)),
        ]
        metadata: dict[str, str] = {
            "case": "Floods",
            "description": "Test case for floods",
        }

        display_case_header("FLOODS CASE", opinions, metadata)
        captured = capsys.readouterr()

        output: str = captured.out

        assert "FLOODS CASE - DETAILED ANALYSIS" in output
        assert "Case: Floods" in output
        assert "Description: Test case for floods" in output
        assert "Number of experts: 4" in output
        assert "(even)" in output

    def test_display_case_header_single_expert(self, capsys):
        """Test case header display with single expert."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(1.0, 2.0, 3.0))
        ]
        metadata: dict[str, str] = {
            "case": "Single",
            "description": "Single expert case",
        }

        display_case_header("SINGLE EXPERT", opinions, metadata)
        captured = capsys.readouterr()

        output: str = captured.out

        assert "Number of experts: 1" in output
        assert "(odd)" in output


class TestDisplayCentroid:
    """Test cases for display_centroid function."""

    def test_display_centroid_default_name(self, capsys):
        """Test centroid display with default name."""
        fuzzy_num: FuzzyTriangleNumber = FuzzyTriangleNumber(1.0, 2.0, 3.0)

        display_centroid(fuzzy_num)
        captured = capsys.readouterr()

        output: str = captured.out

        assert "Centroid:" in output
        assert "(1.00 + 2.00 + 3.00) / 3 = 2.00" in output

    def test_display_centroid_custom_name(self, capsys):
        """Test centroid display with custom name."""
        fuzzy_num: FuzzyTriangleNumber = FuzzyTriangleNumber(10.0, 20.0, 30.0)

        display_centroid(fuzzy_num, name="Mean centroid")
        captured = capsys.readouterr()

        output: str = captured.out

        assert "Mean centroid:" in output
        assert "(10.00 + 20.00 + 30.00) / 3 = 20.00" in output

    def test_display_centroid_decimal_precision(self, capsys):
        """Test that centroid displays with 2 decimal precision."""
        fuzzy_num: FuzzyTriangleNumber = FuzzyTriangleNumber(1.234, 2.567, 3.891)

        display_centroid(fuzzy_num, name="Test")
        captured = capsys.readouterr()

        output: str = captured.out

        # Check that values are formatted to 2 decimal places
        assert "1.23" in output
        assert "2.57" in output
        assert "3.89" in output
        # Centroid = (1.234 + 2.567 + 3.891) / 3 = 2.564
        assert "2.56" in output

    def test_display_centroid_with_equal_values(self, capsys):
        """Test centroid display when all values are equal."""
        fuzzy_num: FuzzyTriangleNumber = FuzzyTriangleNumber(5.0, 5.0, 5.0)

        display_centroid(fuzzy_num, name="Equal")
        captured = capsys.readouterr()

        output: str = captured.out

        assert "Equal:" in output
        assert "(5.00 + 5.00 + 5.00) / 3 = 5.00" in output

    def test_display_centroid_starts_with_newline(self, capsys):
        """Test that centroid display starts with newline for spacing."""
        fuzzy_num: FuzzyTriangleNumber = FuzzyTriangleNumber(1.0, 2.0, 3.0)

        display_centroid(fuzzy_num)
        captured = capsys.readouterr()

        assert captured.out.startswith("\n")

    def test_display_centroid_real_world_budget_example(self, capsys):
        """Test centroid display with real Budget case values."""
        # From Budget case: Mean = (58.14, 67.86, 77.57)
        fuzzy_num: FuzzyTriangleNumber = FuzzyTriangleNumber(58.14, 67.86, 77.57)

        display_centroid(fuzzy_num, name="Arithmetic mean centroid")
        captured = capsys.readouterr()

        output: str = captured.out

        assert "Arithmetic mean centroid:" in output
        assert "58.14" in output
        assert "67.86" in output
        assert "77.57" in output
        # Centroid = (58.14 + 67.86 + 77.57) / 3 = 67.857... ≈ 67.86
        assert "67.86" in output


class TestFormattingIntegration:
    """Integration tests for formatting functions working together."""

    def test_header_and_section_combination(self, capsys):
        """Test using header and section together."""
        print_header("Main Title")
        print_section("Subsection")
        captured = capsys.readouterr()

        output: str = captured.out

        assert "Main Title" in output
        assert "=" in output  # From header
        assert "Subsection" in output
        assert "-" in output  # From section

    def test_complete_case_display_flow(self, capsys):
        """Test complete display flow for a case study."""
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(1.0, 2.0, 3.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(2.0, 3.0, 4.0)),
            ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(3.0, 4.0, 5.0)),
        ]
        metadata: dict[str, str] = {
            "case": "Test",
            "description": "Integration test",
        }

        display_case_header("TEST CASE", opinions, metadata)
        display_centroid(FuzzyTriangleNumber(2.0, 3.0, 4.0), name="Result")
        captured = capsys.readouterr()

        output: str = captured.out

        # Verify all components are present
        assert "TEST CASE - DETAILED ANALYSIS" in output
        assert "Number of experts: 3" in output
        assert "Result:" in output
        assert "(2.00 + 3.00 + 4.00) / 3 = 3.00" in output
