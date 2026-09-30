"""Tests for the system prompt and the context-block renderer."""

import re
from datetime import UTC, datetime

import pytest

from api.assistant.agent.checks import find_ungrounded_numbers
from api.assistant.agent.prompt import (
    FORMULA_NUMBERS,
    PINNED_FACTS,
    PINNED_NUMBERS,
    STYLE,
    SYSTEM_PROMPT,
    format_excerpt,
    format_number,
    render_context_block,
)
from api.assistant.rag.retrieval import RetrievedChunk
from api.assistant.views import FuzzyView, ResultView
from api.db.models import Project
from api.services.agreement_level import derive_agreement


def _chunk(
    chunk_text: str = "The best compromise is the midpoint.",
    *,
    title: str = "Method",
    section: str = "Step 3",
    text: str | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        text=text if text is not None else chunk_text,
        title=title,
        section=section,
        url=None,
        layer="public",
        score=0.5,
        chunk_text=chunk_text,
    )


def _result(
    *,
    max_error: float = 5.974358974358974,
    likert_value: int | None = None,
    likert_decision: str | None = None,
) -> ResultView:
    return ResultView(
        best_compromise=FuzzyView(lower=11.54, peak=14.19, upper=17.19, centroid=14.31),
        arithmetic_mean=FuzzyView(lower=17.08, peak=20.38, upper=23.38, centroid=20.28),
        median=FuzzyView(lower=6.0, peak=8.0, upper=11.0, centroid=8.33),
        max_error=max_error,
        num_experts=13,
        agreement_level="high",
        likert_value=likert_value,
        likert_decision=likert_decision,
        calculated_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


class TestSystemPrompt:
    """The prompt is assembled from its two blocks, and the pinned numbers come from it."""

    def test_is_built_from_the_style_and_the_pinned_facts(self):
        """
        GIVEN the prompt's two named blocks
        WHEN the prompt is assembled
        THEN it contains both, style first
        """
        assert STYLE in SYSTEM_PROMPT
        assert PINNED_FACTS in SYSTEM_PROMPT
        assert SYSTEM_PROMPT.index(STYLE) < SYSTEM_PROMPT.index(PINNED_FACTS)

    def test_every_pinned_number_is_stated_in_the_pinned_facts(self):
        """
        GIVEN the numbers the prompt hands the model
        WHEN they are looked up in the pinned facts
        THEN each one occurs there
        """
        assert PINNED_NUMBERS
        assert all(number in PINNED_FACTS for number in PINNED_NUMBERS)

    def test_the_project_data_rule_is_in_the_style_block(self):
        """
        GIVEN the style block
        WHEN it is searched for the user-text rule
        THEN it names the project_data tags
        """
        assert "<project_data>" in STYLE


class TestPinnedThresholds:
    """The thresholds the prompt states are the ones the agreement rule applies."""

    @pytest.mark.parametrize("number", PINNED_NUMBERS)
    def test_the_agreement_label_changes_just_above_each_pinned_percent(self, number: str):
        """
        GIVEN a scale 100 wide that does not start at zero
        WHEN the error is exactly the pinned percent of the width, and just above it
        THEN the agreement rule gives the two errors different labels
        """
        project = Project(name="P", scale_min=-50.0, scale_max=50.0, scale_unit="%")
        at_threshold = derive_agreement(project, float(number))
        just_above = derive_agreement(project, float(number) + 0.5)

        assert at_threshold != just_above

    def test_the_pinned_facts_state_no_other_number(self):
        """
        GIVEN the pinned facts
        WHEN their digit runs are collected
        THEN they are exactly the pinned numbers
        """
        assert set(re.findall(r"[0-9]+", PINNED_FACTS)) == set(PINNED_NUMBERS)


class TestFormulaNumbers:
    """The divisors of the method's own formulas ground an answer that states them."""

    def test_passed_as_grounding_they_let_the_formulas_through(self):
        """
        GIVEN an answer that states the midpoint and centroid formulas
        WHEN the numbers are checked with the formula numbers as grounding, and without
        THEN nothing is flagged with them, and 2 and 3 are flagged without them
        """
        answer = "The midpoint divides by 2 and the centroid is (a + b + c) / 3."

        assert find_ungrounded_numbers(answer, [*PINNED_NUMBERS, *FORMULA_NUMBERS]) == []
        assert find_ungrounded_numbers(answer, list(PINNED_NUMBERS)) == ["2", "3"]


class TestFormatNumber:
    """Numbers are written with two decimals, the way the UI shows them."""

    def test_rounds_to_two_decimals(self):
        """
        GIVEN a float with a long fraction
        WHEN it is formatted
        THEN two decimals remain
        """
        assert format_number(5.974358974358974) == "5.97"

    def test_pads_a_whole_float_with_zeros(self):
        """
        GIVEN a whole-valued float
        WHEN it is formatted
        THEN two zero decimals are added
        """
        assert format_number(6.0) == "6.00"


class TestFormatExcerpt:
    """One numbered excerpt, as the model is shown it."""

    def test_shows_number_title_section_and_the_chunks_own_words(self):
        """
        GIVEN a chunk whose indexed text carries a generated caption
        WHEN the excerpt is formatted
        THEN the entry has the marker, title, section and chunk_text only
        """
        chunk = _chunk("Own words.", text="Method. A caption.\n\nOwn words.")

        assert format_excerpt(4, chunk) == "[4] Method - Step 3\nOwn words."

    def test_leaves_out_an_empty_section(self):
        """
        GIVEN a chunk with no section
        WHEN the excerpt is formatted
        THEN the heading line has no dangling dash
        """
        assert format_excerpt(1, _chunk("Words.", section="")) == "[1] Method\nWords."


class TestRenderContextBlock:
    """Retrieved chunks and the current project's result render into one block."""

    def test_empty_when_nothing_to_show(self):
        """
        GIVEN no chunks and no project
        WHEN the block is rendered
        THEN it is empty
        """
        assert render_context_block([], None) == ""

    def test_numbers_chunks_and_shows_their_own_words(self):
        """
        GIVEN a chunk whose indexed text carries a caption
        WHEN the block is rendered
        THEN it shows the number, title, section and chunk_text, not the indexed text
        """
        chunk = _chunk(
            "The best compromise is the midpoint.",
            text="Method. A generated caption.\n\nThe best compromise is the midpoint.",
        )

        block = render_context_block([(1, chunk)], None)

        assert block == ("Excerpts:\n\n[1] Method - Step 3\nThe best compromise is the midpoint.")
        assert "generated caption" not in block

    def test_separates_several_chunks_with_a_blank_line(self):
        """
        GIVEN two numbered chunks
        WHEN the block is rendered
        THEN their entries are separated by one blank line, in the order given
        """
        block = render_context_block([(2, _chunk("second")), (5, _chunk("fifth"))], None)

        assert block == "Excerpts:\n\n[2] Method - Step 3\nsecond\n\n[5] Method - Step 3\nfifth"

    def test_an_empty_section_leaves_no_dangling_dash(self):
        """
        GIVEN a chunk with no section
        WHEN the block is rendered
        THEN the heading line is the number and title alone
        """
        block = render_context_block([(1, _chunk("words", section=""))], None)

        assert "[1] Method\nwords" in block
        assert " - " not in block

    def test_wraps_the_project_result_in_project_data_tags(self):
        """
        GIVEN a project result and no chunks
        WHEN the block is rendered
        THEN the result sits inside project_data tags and no excerpts header appears
        """
        block = render_context_block([], _result())

        assert block.startswith("<project_data>\n")
        assert block.endswith("\n</project_data>")
        assert "Excerpts:" not in block

    def test_writes_every_float_with_two_decimals(self):
        """
        GIVEN a maximum error with a long fraction and a whole-number median peak
        WHEN the block is rendered
        THEN floats show two decimals and the expert count stays an integer
        """
        block = render_context_block([], _result())

        assert "5.97" in block
        assert "5.974" not in block
        assert "peak=8.00" in block
        assert "Number of experts: 13\n" in block

    def test_shows_the_centroids_of_the_mean_and_the_median(self):
        """
        GIVEN a project result
        WHEN the block is rendered
        THEN the compromise, the mean and the median each show their centroid
        """
        block = render_context_block([], _result())

        assert "centroid=14.31" in block
        assert "centroid=20.28" in block
        assert "centroid=8.33" in block

    def test_shows_the_agreement_level(self):
        """
        GIVEN a project result with agreement level "high"
        WHEN the block is rendered
        THEN the level is in the block
        """
        assert "Agreement level: high" in render_context_block([], _result())

    def test_the_likert_line_appears_only_with_a_value_and_a_decision(self):
        """
        GIVEN results with both Likert fields, with neither, and with only one of them
        WHEN the blocks are rendered
        THEN only the first has the Likert line, and no line reads "None"
        """
        both = render_context_block([], _result(likert_value=4, likert_decision="agree"))
        neither = render_context_block([], _result())
        value_only = render_context_block([], _result(likert_value=4))
        decision_only = render_context_block([], _result(likert_decision="agree"))

        assert "Likert reading: 4 (agree)" in both
        assert "Likert" not in neither
        assert "Likert" not in value_only
        assert "Likert" not in decision_only
        assert "None" not in value_only

    def test_puts_the_excerpts_before_the_project_data(self):
        """
        GIVEN a chunk and a project result
        WHEN the block is rendered
        THEN the excerpts come first, then a blank line, then the project data
        """
        block = render_context_block([(1, _chunk("words"))], _result())

        assert block.index("Excerpts:") < block.index("<project_data>")
        assert "words\n\n<project_data>" in block
