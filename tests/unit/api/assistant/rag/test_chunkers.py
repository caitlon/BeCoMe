"""Unit tests for chunking loaded Documents (fakes only, no network)."""

import dataclasses

import pytest
from langchain_core.documents import Document

from api.assistant.rag.chunkers import ChunkerConfig, split


def _doc(text: str) -> Document:
    """A Document with the eight base metadata keys loaders.py always sets."""
    return Document(
        page_content=text,
        metadata={
            "source": "docs/method-description.md",
            "layer": "public",
            "title": "Method",
            "lang": "en",
            "url": None,
            "sha256": "abc123",
            "heading_path": "",
            "wave": 1,
        },
    )


class TestChunkerConfig:
    """ChunkerConfig is the frozen dataclass the contract fixes."""

    def test_is_frozen(self):
        """
        GIVEN a constructed ChunkerConfig
        WHEN a field is assigned after construction
        THEN it raises, since chunker configs are immutable
        """
        config = ChunkerConfig(strategy="markdown_headers")
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.size = 999

    def test_defaults(self):
        """
        GIVEN a ChunkerConfig built with only strategy given
        WHEN its other fields are read
        THEN size is 500 and overlap_pct is 10, the contracted defaults
        """
        config = ChunkerConfig(strategy="markdown_headers")
        assert config.size == 500
        assert config.overlap_pct == 10


class TestMarkdownHeadersStrategy:
    """The only strategy implemented in this pull request."""

    def test_splits_by_heading_and_keeps_the_heading_out_of_the_body_text(self):
        """
        GIVEN one document with two H2 sections under one H1
        WHEN split() runs with markdown_headers and a generous size
        THEN each section is its own chunk, heading_path joins h1>h2, the heading
             line itself is not in the chunk body, and provenance metadata survives
        """
        # GIVEN
        text = (
            "# Method\n\n"
            "## Best compromise\n\n"
            "It is the midpoint of the mean and the median.\n\n"
            "## Maximum error\n\n"
            "It measures how far the mean and median sit apart.\n"
        )
        config = ChunkerConfig(strategy="markdown_headers", size=500, overlap_pct=10)

        # WHEN
        chunks = split([_doc(text)], config)

        # THEN
        by_heading = {c.metadata["heading_path"]: c.page_content for c in chunks}
        assert (
            by_heading["Method > Best compromise"]
            == "It is the midpoint of the mean and the median."
        )
        assert by_heading["Method > Maximum error"] == (
            "It measures how far the mean and median sit apart."
        )
        assert "# Method" not in by_heading["Method > Best compromise"]
        assert all(c.metadata["source"] == "docs/method-description.md" for c in chunks)
        assert all(c.metadata["sha256"] == "abc123" for c in chunks)

    def test_bounds_an_oversized_section_into_several_same_heading_chunks(self):
        """
        GIVEN one section whose body exceeds config.size
        WHEN split() runs with a small size and no overlap
        THEN it becomes several chunks, each within size, all under the same heading
        """
        # GIVEN
        text = (
            "## Best compromise\n\n"
            "It is the midpoint of the mean and the median, computed component by "
            "component across lower bound, peak, and upper bound.\n"
        )
        config = ChunkerConfig(strategy="markdown_headers", size=60, overlap_pct=0)

        # WHEN
        chunks = split([_doc(text)], config)

        # THEN: exact pieces, verified directly against this langchain-text-splitters
        # version (2026-09-14) rather than assumed - the splitter's break points are
        # an implementation detail this test pins down, not a value to guess at.
        assert [c.page_content for c in chunks] == [
            "It is the midpoint of the mean and the median, computed",
            "component by component across lower bound, peak, and upper",
            "bound.",
        ]
        assert all(c.metadata["heading_path"] == "Best compromise" for c in chunks)
        assert all(len(c.page_content) <= 60 for c in chunks)

    def test_a_document_with_no_headings_becomes_one_heading_path_of_empty_string(self):
        """
        GIVEN a document with no "#"-prefixed lines (a PDF's or LaTeX's plain text)
        WHEN split() runs with markdown_headers
        THEN it still produces a chunk, with heading_path "" rather than raising
        """
        # GIVEN
        text = "Plain text extracted from a PDF. No markdown headings appear in it."
        config = ChunkerConfig(strategy="markdown_headers", size=500, overlap_pct=10)

        # WHEN
        chunks = split([_doc(text)], config)

        # THEN
        assert len(chunks) == 1
        assert chunks[0].metadata["heading_path"] == ""
        assert chunks[0].page_content == text


class TestUnimplementedStrategies:
    """Every strategy but markdown_headers is left for later, and fails loudly."""

    @pytest.mark.parametrize(
        "strategy", ["fixed", "recursive", "sentences", "semantic", "parent_child"]
    )
    def test_raises_not_implemented(self, strategy):
        """
        GIVEN a ChunkerConfig using a strategy this pull request does not implement
        WHEN split() is called
        THEN it raises NotImplementedError naming the strategy
        """
        config = ChunkerConfig(strategy=strategy)
        with pytest.raises(NotImplementedError, match=strategy):
            split([_doc("text")], config)
