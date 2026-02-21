"""Unit tests for examples.utils.data_loading module."""

import pytest

from examples.utils.data_loading import _parse_expert_line, _parse_metadata_line, load_data_from_txt


class TestParseMetadataLine:
    """Test cases for _parse_metadata_line helper."""

    @pytest.mark.parametrize(
        "line,expected_key,expected_value",
        [
            ("CASE: Budget", "case", "Budget"),
            ("DESCRIPTION: Some description", "description", "Some description"),
            ("EXPERTS: 22", "num_experts", "22"),
        ],
    )
    def test_recognized_prefixes(self, line: str, expected_key: str, expected_value: str) -> None:
        """Test that known metadata prefixes are parsed correctly."""
        # GIVEN
        metadata: dict[str, str] = {}

        # WHEN
        result = _parse_metadata_line(line, metadata)

        # THEN
        assert result is True
        assert metadata[expected_key] == expected_value

    def test_non_metadata_line_returns_false(self) -> None:
        """Test that a non-metadata line is not parsed."""
        # GIVEN
        metadata: dict[str, str] = {}

        # WHEN
        result = _parse_metadata_line("Expert1 | 10 | 20 | 30", metadata)

        # THEN
        assert result is False
        assert metadata == {}

    def test_comment_line_returns_false(self) -> None:
        """Test that a comment-like line is not parsed as metadata."""
        # GIVEN
        metadata: dict[str, str] = {}

        # WHEN
        result = _parse_metadata_line("# This is a comment", metadata)

        # THEN
        assert result is False

    def test_experts_prefix_maps_to_num_experts_key(self) -> None:
        """Test that EXPERTS: prefix produces 'num_experts' key."""
        # GIVEN
        metadata: dict[str, str] = {}

        # WHEN
        _parse_metadata_line("EXPERTS: 13", metadata)

        # THEN
        assert "num_experts" in metadata
        assert "experts" not in metadata

    def test_metadata_value_whitespace_stripped(self) -> None:
        """Test that leading/trailing whitespace is stripped from metadata values."""
        # GIVEN
        metadata: dict[str, str] = {}

        # WHEN
        _parse_metadata_line("CASE:   Budget Support  ", metadata)

        # THEN
        assert metadata["case"] == "Budget Support"


class TestParseExpertLine:
    """Test cases for _parse_expert_line helper."""

    def test_valid_line_parsing(self) -> None:
        """Test parsing a well-formed expert opinion line."""
        # WHEN
        opinion = _parse_expert_line("Expert1 | 10 | 20 | 30")

        # THEN
        assert opinion.expert_id == "Expert1"
        assert opinion.opinion.lower_bound == 10.0
        assert opinion.opinion.peak == 20.0
        assert opinion.opinion.upper_bound == 30.0

    def test_float_values(self) -> None:
        """Test parsing expert line with float values."""
        # WHEN
        opinion = _parse_expert_line("E1 | 10.5 | 20.7 | 30.9")

        # THEN
        assert opinion.opinion.lower_bound == 10.5
        assert opinion.opinion.peak == 20.7
        assert opinion.opinion.upper_bound == 30.9

    def test_expert_id_with_spaces(self) -> None:
        """Test parsing expert ID containing spaces."""
        # WHEN
        opinion = _parse_expert_line("Deputy Minister of MF | 30 | 45 | 70")

        # THEN
        assert opinion.expert_id == "Deputy Minister of MF"

    def test_wrong_number_of_parts_raises_value_error(self) -> None:
        """Test that a line with wrong number of pipe-separated parts raises ValueError."""
        # WHEN/THEN
        with pytest.raises(ValueError, match="expected 4 parts"):
            _parse_expert_line("Expert1 | 10 | 20")

    def test_non_numeric_values_raise_value_error(self) -> None:
        """Test that non-numeric values raise ValueError."""
        # WHEN/THEN
        with pytest.raises(ValueError, match="Invalid numeric"):
            _parse_expert_line("Expert1 | abc | 20 | 30")

    def test_empty_parts_raise_value_error(self) -> None:
        """Test that a line with too many parts raises ValueError."""
        # WHEN/THEN
        with pytest.raises(ValueError, match="expected 4 parts"):
            _parse_expert_line("E1 | 10 | 20 | 30 | 40")


class TestLoadDataFromTxtValidation:
    """Test load_data_from_txt validation of unrecognized lines."""

    def test_unrecognized_line_raises_value_error(self, tmp_path) -> None:
        """Test that a line matching no known format raises ValueError."""
        # GIVEN
        data_file = tmp_path / "bad_data.txt"
        data_file.write_text("CASE: Test\nsome garbage line\n", encoding="utf-8")

        # WHEN/THEN
        with pytest.raises(ValueError, match="Unrecognized line format"):
            load_data_from_txt(str(data_file))

    def test_valid_file_loads_successfully(self, tmp_path) -> None:
        """Test that a well-formed file loads without errors."""
        # GIVEN
        data_file = tmp_path / "good_data.txt"
        data_file.write_text(
            "CASE: Test\n"
            "DESCRIPTION: A test\n"
            "EXPERTS: 1\n"
            "\n"
            "# comment\n"
            "Expert1 | 10 | 20 | 30\n",
            encoding="utf-8",
        )

        # WHEN
        opinions, metadata = load_data_from_txt(str(data_file))

        # THEN
        assert len(opinions) == 1
        assert metadata["case"] == "Test"
