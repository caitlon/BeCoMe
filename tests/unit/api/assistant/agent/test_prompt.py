"""Tests for the system prompt and the context-block renderer."""

from datetime import UTC, datetime

from api.assistant.agent.prompt import (
    PINNED_FACTS,
    PINNED_NUMBERS,
    STYLE,
    SYSTEM_PROMPT,
    render_context_block,
)
from api.assistant.rag.retrieval import RetrievedChunk
from api.assistant.views import FuzzyView, ResultView


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

    def test_the_likert_line_appears_only_with_a_value(self):
        """
        GIVEN one result with a Likert value and one without
        WHEN both blocks are rendered
        THEN only the first has the Likert line
        """
        with_value = render_context_block([], _result(likert_value=4, likert_decision="agree"))
        without = render_context_block([], _result())

        assert "Likert reading: 4 (agree)" in with_value
        assert "Likert" not in without

    def test_puts_the_excerpts_before_the_project_data(self):
        """
        GIVEN a chunk and a project result
        WHEN the block is rendered
        THEN the excerpts come first, then a blank line, then the project data
        """
        block = render_context_block([(1, _chunk("words"))], _result())

        assert block.index("Excerpts:") < block.index("<project_data>")
        assert "words\n\n<project_data>" in block
