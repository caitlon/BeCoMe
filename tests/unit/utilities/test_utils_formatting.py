"""
Unit tests for examples.utils.formatting module.

Tests the console output formatting functions used to display
case study information and results in a structured format.

Following Lott's "Python Object-Oriented Programming" (Chapter 13):
- Tests structured as GIVEN-WHEN-THEN
- Parametrization reduces code duplication (DRY principle)
- Each test validates a single behavior
- capsys fixture used to test console output
"""

import pytest

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

    @pytest.mark.parametrize(
        "title,width",
        [
            ("Test Title", 60),  # Default width
            ("Short", 40),  # Custom width
            ("BUDGET CASE - DETAILED ANALYSIS", 70),  # Long title
        ],
    )
    def test_print_header_format(self, capsys, title: str, width: int) -> None:
        """
        Test header printing with various titles and widths.

        GIVEN: A title string and width
        WHEN: Printing a header
        THEN: Output has correct format with separators and centered title
        """
        # GIVEN: title and width provided by parametrize

        # WHEN: Print header
        print_header(title, width=width)
        captured = capsys.readouterr()

        lines: list[str] = captured.out.strip().split("\n")

        # THEN: Format is correct (newline, separator, centered title, separator)
        assert captured.out.startswith("\n")
        assert len(lines) == 3
        assert lines[0] == "=" * width
        assert lines[1] == title.center(width)
        assert lines[2] == "=" * width


class TestPrintSection:
    """Test cases for print_section function."""

    @pytest.mark.parametrize(
        "title,width",
        [
            ("Section Title", 60),  # Default width
            ("Step 1", 40),  # Custom width
        ],
    )
    def test_print_section_format(self, capsys, title: str, width: int) -> None:
        """
        Test section printing with various titles and widths.

        GIVEN: A section title and width
        WHEN: Printing a section separator
        THEN: Output has correct format with dashes and title
        """
        # GIVEN: title and width provided by parametrize

        # WHEN: Print section
        print_section(title, width=width)
        captured = capsys.readouterr()

        output: str = captured.out.strip()

        # THEN: Format is correct (newline, dashes with title)
        assert captured.out.startswith("\n")
        assert f" {title} " in output
        assert "-" in output


class TestDisplayCaseHeader:
    """Test cases for display_case_header function."""

    @pytest.mark.parametrize(
        "case_name,num_experts,metadata_case,description,expected_parity",
        [
            ("BUDGET CASE", 3, "Budget", "Test case for budget", "odd"),
            ("FLOODS CASE", 4, "Floods", "Test case for floods", "even"),
            ("SINGLE EXPERT", 1, "Single", "Single expert case", "odd"),
        ],
    )
    def test_display_case_header_format(
        self,
        capsys,
        opinions_factory,
        case_name: str,
        num_experts: int,
        metadata_case: str,
        description: str,
        expected_parity: str,
    ) -> None:
        """
        Test case header display with different expert counts.

        GIVEN: Case name, expert opinions, and metadata
        WHEN: Displaying case header
        THEN: Output contains case info and expert count with parity
        """
        # GIVEN: Create simple opinions using factory (all with same fuzzy number)
        # For header display, the actual fuzzy values don't matter
        all_opinions = opinions_factory(num_experts if num_experts > 0 else 1, is_likert=False)
        opinions: list[ExpertOpinion] = all_opinions[:num_experts] if num_experts > 0 else []

        metadata: dict[str, str] = {
            "case": metadata_case,
            "description": description,
        }

        # WHEN: Display case header
        display_case_header(case_name, opinions, metadata)
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN: Output contains all case information
        assert f"{case_name} - DETAILED ANALYSIS" in output
        assert f"Case: {metadata_case}" in output
        assert f"Description: {description}" in output
        assert f"Number of experts: {num_experts}" in output
        assert f"({expected_parity})" in output


class TestDisplayCentroid:
    """Test cases for display_centroid function."""

    @pytest.mark.parametrize(
        "lower,peak,upper,name,expected_output",
        [
            (1.0, 2.0, 3.0, "Centroid", "(1.00 + 2.00 + 3.00) / 3 = 2.00"),
            (10.0, 20.0, 30.0, "Mean centroid", "(10.00 + 20.00 + 30.00) / 3 = 20.00"),
            (5.0, 5.0, 5.0, "Equal", "(5.00 + 5.00 + 5.00) / 3 = 5.00"),
        ],
    )
    def test_display_centroid_format(
        self,
        capsys,
        lower: float,
        peak: float,
        upper: float,
        name: str,
        expected_output: str,
    ) -> None:
        """
        Test centroid display with various values and names.

        GIVEN: A fuzzy triangular number and centroid name
        WHEN: Displaying the centroid
        THEN: Output shows calculation formula and result with 2 decimal precision
        """
        # GIVEN: Create fuzzy number with specified bounds
        fuzzy_num: FuzzyTriangleNumber = FuzzyTriangleNumber(lower, peak, upper)

        # WHEN: Display centroid
        display_centroid(fuzzy_num, name=name)
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN: Format is correct (newline, name, and calculation)
        assert captured.out.startswith("\n")
        assert f"{name}:" in output
        assert expected_output in output

    def test_display_centroid_decimal_precision(self, capsys) -> None:
        """
        Test that centroid displays with 2 decimal precision.

        GIVEN: A fuzzy number with high-precision decimal values
        WHEN: Displaying the centroid
        THEN: All values are formatted to exactly 2 decimal places
        """
        # GIVEN: Fuzzy number with high-precision decimals
        fuzzy_num: FuzzyTriangleNumber = FuzzyTriangleNumber(1.234, 2.567, 3.891)

        # WHEN: Display centroid
        display_centroid(fuzzy_num, name="Test")
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN: Values are formatted to 2 decimal places
        assert "1.23" in output
        assert "2.57" in output
        assert "3.89" in output
        # THEN: Centroid = (1.234 + 2.567 + 3.891) / 3 = 2.564 → 2.56
        assert "2.56" in output


class TestFormattingErrorHandling:
    """Test error handling in formatting functions."""

    def test_print_header_with_none_title_raises_error(self) -> None:
        """
        Test that None title raises AttributeError.

        GIVEN: None instead of title string
        WHEN: Attempting to print header
        THEN: AttributeError is raised
        """
        # GIVEN: None title

        # WHEN/THEN: Calling print_header should raise AttributeError
        with pytest.raises(AttributeError):
            print_header(None)  # type: ignore

    def test_print_section_with_none_title_raises_error(self) -> None:
        """
        Test that None title raises TypeError in print_section.

        GIVEN: None instead of title string
        WHEN: Attempting to print section
        THEN: TypeError is raised
        """
        # GIVEN: None title

        # WHEN/THEN: Calling print_section should raise TypeError
        with pytest.raises(TypeError):
            print_section(None)  # type: ignore

    def test_display_case_header_with_none_opinions_raises_error(self) -> None:
        """
        Test that None opinions raise TypeError in display_case_header.

        GIVEN: Valid case name and metadata but None opinions
        WHEN: Attempting to display case header
        THEN: TypeError is raised
        """
        # GIVEN: Valid case name and metadata, None opinions
        metadata: dict[str, str] = {"case": "Test", "description": "Test case"}

        # WHEN/THEN: Calling display_case_header should raise TypeError
        with pytest.raises(TypeError):
            display_case_header("TEST CASE", None, metadata)  # type: ignore

    def test_display_case_header_with_none_metadata_raises_error(self) -> None:
        """
        Test that None metadata raises TypeError in display_case_header.

        GIVEN: Valid case name and opinions but None metadata
        WHEN: Attempting to display case header
        THEN: TypeError is raised
        """
        # GIVEN: Valid case name and opinions, None metadata
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(1.0, 2.0, 3.0))
        ]

        # WHEN/THEN: Calling display_case_header should raise TypeError
        with pytest.raises(TypeError):
            display_case_header("TEST CASE", opinions, None)  # type: ignore

    def test_display_case_header_with_empty_opinions_list(self) -> None:
        """
        Test that empty opinions list displays correctly.

        GIVEN: Empty opinions list
        WHEN: Displaying case header
        THEN: Header displays with 0 experts (even)
        """
        # GIVEN: Empty opinions list
        opinions: list[ExpertOpinion] = []
        metadata: dict[str, str] = {"case": "Empty", "description": "No experts"}

        # WHEN: Display case header (should not raise)
        # This is actually valid - might represent a case with no opinions yet
        display_case_header("EMPTY CASE", opinions, metadata)

        # THEN: No error raised (function handles gracefully)

    def test_display_centroid_with_none_fuzzy_number_raises_error(self) -> None:
        """
        Test that None fuzzy number raises AttributeError.

        GIVEN: None instead of FuzzyTriangleNumber
        WHEN: Attempting to display centroid
        THEN: AttributeError is raised
        """
        # GIVEN: None fuzzy number

        # WHEN/THEN: Calling display_centroid should raise AttributeError
        with pytest.raises(AttributeError):
            display_centroid(None, name="Test")  # type: ignore
