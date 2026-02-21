"""Unit tests for examples.utils.labels and examples.utils.locales modules."""

import dataclasses

import pytest

from examples.utils.labels import AnalysisLabels, DisplayLabels, FormattingLabels
from examples.utils.locales import (
    CS_ANALYSIS,
    CS_DISPLAY,
    CS_FORMATTING,
    EN_ANALYSIS,
    EN_DISPLAY,
    EN_FORMATTING,
)


class TestDisplayLabelsImmutability:
    """Test that DisplayLabels instances are truly frozen."""

    def test_cannot_modify_field(self) -> None:
        """Test that assigning to a field raises FrozenInstanceError."""
        # WHEN/THEN
        with pytest.raises(dataclasses.FrozenInstanceError):
            EN_DISPLAY.step_1_title = "changed"  # type: ignore[misc]

    def test_cannot_delete_field(self) -> None:
        """Test that deleting a field raises FrozenInstanceError."""
        # WHEN/THEN
        with pytest.raises(dataclasses.FrozenInstanceError):
            del EN_DISPLAY.step_1_title  # type: ignore[misc]


class TestFormattingLabelsImmutability:
    """Test that FormattingLabels instances are truly frozen."""

    def test_cannot_modify_field(self) -> None:
        """Test that assigning to a field raises FrozenInstanceError."""
        # WHEN/THEN
        with pytest.raises(dataclasses.FrozenInstanceError):
            EN_FORMATTING.case_label = "changed"  # type: ignore[misc]


class TestAnalysisLabelsImmutability:
    """Test that AnalysisLabels instances are truly frozen."""

    def test_cannot_modify_field(self) -> None:
        """Test that assigning to a field raises FrozenInstanceError."""
        # WHEN/THEN
        with pytest.raises(dataclasses.FrozenInstanceError):
            EN_ANALYSIS.good = "changed"  # type: ignore[misc]


class TestEnglishLocaleCompleteness:
    """Verify that EN locale instances have all fields populated."""

    def test_en_display_all_fields_non_empty(self) -> None:
        """Test that every EN_DISPLAY field is a non-empty string."""
        # WHEN/THEN
        for field in dataclasses.fields(EN_DISPLAY):
            value = getattr(EN_DISPLAY, field.name)
            assert isinstance(value, str), f"{field.name} is not str"
            assert value, f"{field.name} is empty"

    def test_en_formatting_all_fields_non_empty(self) -> None:
        """Test that every EN_FORMATTING field is a non-empty string."""
        # WHEN/THEN
        for field in dataclasses.fields(EN_FORMATTING):
            value = getattr(EN_FORMATTING, field.name)
            assert isinstance(value, str), f"{field.name} is not str"
            assert value, f"{field.name} is empty"

    def test_en_analysis_all_fields_non_empty(self) -> None:
        """Test that every EN_ANALYSIS field is a non-empty string."""
        # WHEN/THEN
        for field in dataclasses.fields(EN_ANALYSIS):
            value = getattr(EN_ANALYSIS, field.name)
            assert isinstance(value, str), f"{field.name} is not str"
            assert value, f"{field.name} is empty"


class TestCzechLocaleCompleteness:
    """Verify that CS locale instances have all fields populated."""

    def test_cs_display_all_fields_non_empty(self) -> None:
        """Test that every CS_DISPLAY field is a non-empty string."""
        # WHEN/THEN
        for field in dataclasses.fields(CS_DISPLAY):
            value = getattr(CS_DISPLAY, field.name)
            assert isinstance(value, str), f"{field.name} is not str"
            assert value, f"{field.name} is empty"

    def test_cs_formatting_all_fields_non_empty(self) -> None:
        """Test that every CS_FORMATTING field is a non-empty string."""
        # WHEN/THEN
        for field in dataclasses.fields(CS_FORMATTING):
            value = getattr(CS_FORMATTING, field.name)
            assert isinstance(value, str), f"{field.name} is not str"
            assert value, f"{field.name} is empty"

    def test_cs_analysis_all_fields_non_empty(self) -> None:
        """Test that every CS_ANALYSIS field is a non-empty string."""
        # WHEN/THEN
        for field in dataclasses.fields(CS_ANALYSIS):
            value = getattr(CS_ANALYSIS, field.name)
            assert isinstance(value, str), f"{field.name} is not str"
            assert value, f"{field.name} is empty"


class TestLocaleFieldParity:
    """Verify that EN and CS locales have matching field sets."""

    def test_display_same_fields(self) -> None:
        """Test that EN_DISPLAY and CS_DISPLAY have identical field names."""
        # GIVEN
        en_fields = {f.name for f in dataclasses.fields(EN_DISPLAY)}

        # WHEN
        cs_fields = {f.name for f in dataclasses.fields(CS_DISPLAY)}

        # THEN
        assert en_fields == cs_fields

    def test_formatting_same_fields(self) -> None:
        """Test that EN_FORMATTING and CS_FORMATTING have identical field names."""
        # GIVEN
        en_fields = {f.name for f in dataclasses.fields(EN_FORMATTING)}

        # WHEN
        cs_fields = {f.name for f in dataclasses.fields(CS_FORMATTING)}

        # THEN
        assert en_fields == cs_fields

    def test_analysis_same_fields(self) -> None:
        """Test that EN_ANALYSIS and CS_ANALYSIS have identical field names."""
        # GIVEN
        en_fields = {f.name for f in dataclasses.fields(EN_ANALYSIS)}

        # WHEN
        cs_fields = {f.name for f in dataclasses.fields(CS_ANALYSIS)}

        # THEN
        assert en_fields == cs_fields


class TestLocaleDistinctValues:
    """Verify that EN and CS locales have different values (not just copies)."""

    def test_display_labels_differ(self) -> None:
        """Test that EN and CS display labels have distinct step titles."""
        # THEN
        assert EN_DISPLAY.step_1_title != CS_DISPLAY.step_1_title
        assert EN_DISPLAY.step_2_title != CS_DISPLAY.step_2_title
        assert EN_DISPLAY.step_3_title != CS_DISPLAY.step_3_title
        assert EN_DISPLAY.step_4_title != CS_DISPLAY.step_4_title

    def test_formatting_labels_differ(self) -> None:
        """Test that EN and CS formatting labels have distinct values."""
        # THEN
        assert EN_FORMATTING.case_label != CS_FORMATTING.case_label
        assert EN_FORMATTING.even_label != CS_FORMATTING.even_label

    def test_analysis_labels_differ(self) -> None:
        """Test that EN and CS analysis labels have distinct values."""
        # THEN
        assert EN_ANALYSIS.good != CS_ANALYSIS.good
        assert EN_ANALYSIS.moderate != CS_ANALYSIS.moderate
        assert EN_ANALYSIS.low != CS_ANALYSIS.low


class TestLabelDataclassCreation:
    """Test creating custom label instances."""

    def test_create_custom_display_labels(self) -> None:
        """Test that custom DisplayLabels can be created with all required fields."""
        # GIVEN
        fields = {f.name: f"test_{f.name}" for f in dataclasses.fields(DisplayLabels)}

        # WHEN
        custom = DisplayLabels(**fields)

        # THEN
        assert custom.step_1_title == "test_step_1_title"

    def test_create_custom_formatting_labels(self) -> None:
        """Test that custom FormattingLabels can be created."""
        # WHEN
        custom = FormattingLabels(
            detailed_analysis="DETAIL",
            case_label="Case",
            description_label="Desc",
            num_experts_label="Experts",
            even_label="even",
            odd_label="odd",
            default_centroid_name="Centroid",
            not_available_label="N/A",
        )

        # THEN
        assert custom.detailed_analysis == "DETAIL"

    def test_create_custom_analysis_labels(self) -> None:
        """Test that custom AnalysisLabels can be created."""
        # WHEN
        custom = AnalysisLabels(good="bueno", moderate="moderado", low="bajo")

        # THEN
        assert custom.good == "bueno"
