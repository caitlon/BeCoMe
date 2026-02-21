"""Unit tests for examples.utils.formatting module."""

import pytest

from examples.utils.formatting import (
    display_case_header,
    display_centroid,
    print_header,
    print_section,
)
from examples.utils.locales import CS_FORMATTING
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
        """Test header printing with various titles and widths."""
        # WHEN
        print_header(title, width=width)
        captured = capsys.readouterr()

        lines: list[str] = captured.out.strip().split("\n")

        # THEN
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
        """Test section printing with various titles and widths."""
        # WHEN
        print_section(title, width=width)
        captured = capsys.readouterr()

        output: str = captured.out.strip()

        # THEN
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
        """Test case header display with different expert counts."""
        # GIVEN
        all_opinions = opinions_factory(num_experts if num_experts > 0 else 1, is_likert=False)
        opinions: list[ExpertOpinion] = all_opinions[:num_experts] if num_experts > 0 else []

        metadata: dict[str, str] = {
            "case": metadata_case,
            "description": description,
        }

        # WHEN
        display_case_header(case_name, opinions, metadata)
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN
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
        """Test centroid display with various values and names."""
        # GIVEN
        fuzzy_num: FuzzyTriangleNumber = FuzzyTriangleNumber(lower, peak, upper)

        # WHEN
        display_centroid(fuzzy_num, name=name)
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN
        assert captured.out.startswith("\n")
        assert f"{name}:" in output
        assert expected_output in output

    def test_display_centroid_decimal_precision(self, capsys) -> None:
        """Test that centroid displays with 2 decimal precision."""
        # GIVEN
        fuzzy_num: FuzzyTriangleNumber = FuzzyTriangleNumber(1.234, 2.567, 3.891)

        # WHEN
        display_centroid(fuzzy_num, name="Test")
        captured = capsys.readouterr()

        output: str = captured.out

        # THEN
        assert "1.23" in output
        assert "2.57" in output
        assert "3.89" in output
        assert "2.56" in output


class TestFormattingErrorHandling:
    """Test error handling in formatting functions."""

    def test_print_header_with_none_title_raises_error(self) -> None:
        """Test that None title raises TypeError."""
        # WHEN/THEN
        with pytest.raises(TypeError):
            print_header(None)  # type: ignore

    def test_print_section_with_none_title_raises_error(self) -> None:
        """Test that None title raises TypeError in print_section."""
        # WHEN/THEN
        with pytest.raises(TypeError):
            print_section(None)  # type: ignore

    def test_display_case_header_with_none_opinions_raises_error(self) -> None:
        """Test that None opinions raise TypeError in display_case_header."""
        # GIVEN
        metadata: dict[str, str] = {"case": "Test", "description": "Test case"}

        # WHEN/THEN
        with pytest.raises(TypeError):
            display_case_header("TEST CASE", None, metadata)  # type: ignore

    def test_display_case_header_with_none_metadata_raises_error(self) -> None:
        """Test that None metadata raises AttributeError in display_case_header."""
        # GIVEN
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(1.0, 2.0, 3.0))
        ]

        # WHEN/THEN
        with pytest.raises(AttributeError):
            display_case_header("TEST CASE", opinions, None)  # type: ignore

    def test_display_case_header_with_empty_opinions_list(self) -> None:
        """Test that empty opinions list displays correctly."""
        # GIVEN
        opinions: list[ExpertOpinion] = []
        metadata: dict[str, str] = {"case": "Empty", "description": "No experts"}

        # WHEN
        display_case_header("EMPTY CASE", opinions, metadata)

    def test_display_centroid_with_none_fuzzy_number_raises_error(self) -> None:
        """Test that None fuzzy number raises AttributeError."""
        # WHEN/THEN
        with pytest.raises(AttributeError):
            display_centroid(None, name="Test")  # type: ignore


class TestFormattingWithCzechLabels:
    """Test formatting functions with Czech labels."""

    def test_display_case_header_czech(self, capsys) -> None:
        """Test case header uses Czech labels."""
        # GIVEN
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(1.0, 2.0, 3.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(4.0, 5.0, 6.0)),
        ]
        metadata: dict[str, str] = {"case": "Test", "description": "Testovací případ"}

        # WHEN
        display_case_header("TESTOVACÍ PŘÍPAD", opinions, metadata, labels=CS_FORMATTING)
        output: str = capsys.readouterr().out

        # THEN
        assert "PODROBNÁ ANALÝZA" in output
        assert "Případ: Test" in output
        assert "Popis: Testovací případ" in output
        assert "Počet expertů: 2 (sudý)" in output

    def test_display_case_header_czech_odd(self, capsys) -> None:
        """Test case header uses Czech odd parity label."""
        # GIVEN
        opinions: list[ExpertOpinion] = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(1.0, 2.0, 3.0)),
        ]
        metadata: dict[str, str] = {"case": "Test", "description": "Popis"}

        # WHEN
        display_case_header("PŘÍPAD", opinions, metadata, labels=CS_FORMATTING)
        output: str = capsys.readouterr().out

        # THEN
        assert "lichý" in output

    def test_display_centroid_czech_default_name(self, capsys) -> None:
        """Test centroid display uses Czech default name when no name given."""
        # GIVEN
        fuzzy_num = FuzzyTriangleNumber(10.0, 20.0, 30.0)

        # WHEN
        display_centroid(fuzzy_num, labels=CS_FORMATTING)
        output: str = capsys.readouterr().out

        # THEN
        assert "Těžiště:" in output
