"""Unit tests for per-chunk context enrichment (fakes only, no network)."""

import pytest
from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from api.assistant.rag.enrich import enrich


def _chunk(
    text: str, heading_path: str = "", source: str = "docs/method-description.md"
) -> Document:
    """A chunk with the metadata keys enrich() reads."""
    return Document(
        page_content=text,
        metadata={
            "source": source,
            "layer": "public",
            "title": "Method",
            "lang": "en",
            "url": None,
            "sha256": "abc",
            "heading_path": heading_path,
            "wave": 1,
        },
    )


class TestNoneMode:
    """mode="none" is a pass-through: no context added."""

    def test_returns_chunks_unchanged(self):
        """
        GIVEN one chunk
        WHEN enrich() runs with mode="none"
        THEN the returned Document has the exact same text and metadata
        """
        # GIVEN
        chunk = _chunk("The compromise is the midpoint of the mean and the median.")

        # WHEN
        enriched = enrich([chunk], mode="none")

        # THEN
        assert enriched[0].page_content == chunk.page_content
        assert enriched[0].metadata == chunk.metadata


class TestHeadingPathMode:
    """mode="heading_path" prepends the chunk's own heading trail to its text."""

    def test_prepends_the_heading_path(self):
        """
        GIVEN a chunk with a non-empty heading_path
        WHEN enrich() runs with mode="heading_path"
        THEN the heading path appears before the chunk's own text, separated by a
             blank line
        """
        # GIVEN
        chunk = _chunk(
            "It is the midpoint of the mean and the median.",
            heading_path="Method > Best compromise",
        )

        # WHEN
        enriched = enrich([chunk], mode="heading_path")

        # THEN
        assert enriched[0].page_content == (
            "Method > Best compromise\n\nIt is the midpoint of the mean and the median."
        )

    def test_leaves_a_headingless_chunk_unchanged(self):
        """
        GIVEN a chunk with an empty heading_path (a header-less document, e.g. a PDF)
        WHEN enrich() runs with mode="heading_path"
        THEN there is nothing to prepend, so the text is unchanged
        """
        # GIVEN
        chunk = _chunk("Plain text with no heading structure.", heading_path="")

        # WHEN
        enriched = enrich([chunk], mode="heading_path")

        # THEN
        assert enriched[0].page_content == "Plain text with no heading structure."


class TestLlmContextMode:
    """mode="llm_context" asks the model what each chunk is about, then prepends it."""

    def test_prepends_the_models_own_context_sentence(self):
        """
        GIVEN a chunk and a fake model with a canned context sentence
        WHEN enrich() runs with mode="llm_context"
        THEN the model's sentence appears before the chunk's own text
        """
        # GIVEN
        chunk = _chunk("It uses every opinion, which is its virtue and its flaw.")
        llm = FakeListChatModel(responses=["Describes a weakness of the arithmetic mean."])

        # WHEN
        enriched = enrich([chunk], mode="llm_context", llm=llm)

        # THEN
        assert enriched[0].page_content == (
            "Describes a weakness of the arithmetic mean.\n\n"
            "It uses every opinion, which is its virtue and its flaw."
        )

    def test_requires_an_llm(self):
        """
        GIVEN mode="llm_context" but llm=None
        WHEN enrich() is called
        THEN it raises ValueError rather than failing deep inside llm.invoke
        """
        # GIVEN / WHEN / THEN
        with pytest.raises(ValueError, match="llm_context"):
            enrich([_chunk("text")], mode="llm_context", llm=None)


class TestDocSummaryMode:
    """mode="doc_summary" prepends one summary per source document, not per chunk."""

    def test_prepends_the_same_summary_to_every_chunk_of_one_source(self):
        """
        GIVEN two chunks from the same source and a fake model with one canned summary
        WHEN enrich() runs with mode="doc_summary"
        THEN both chunks get the SAME summary prepended, and the model was called once
        """
        # GIVEN
        chunks = [
            _chunk("First chunk of the method description."),
            _chunk("Second chunk of the method description."),
        ]
        llm = FakeListChatModel(responses=["A method for aggregating expert opinions."])

        # WHEN
        enriched = enrich(chunks, mode="doc_summary", llm=llm)

        # THEN
        assert enriched[0].page_content == (
            "A method for aggregating expert opinions.\n\nFirst chunk of the method description."
        )
        assert enriched[1].page_content == (
            "A method for aggregating expert opinions.\n\nSecond chunk of the method description."
        )

    def test_summarizes_two_different_sources_separately(self):
        """
        GIVEN chunks from two different sources
        WHEN enrich() runs with mode="doc_summary" and two canned responses
        THEN each source's chunk gets its OWN summary, in call order
        """
        # GIVEN
        chunks = [
            _chunk("About the method.", source="docs/method-description.md"),
            _chunk("About getting started.", source="docs/user/getting-started.md"),
        ]
        llm = FakeListChatModel(responses=["Method summary.", "Getting-started summary."])

        # WHEN
        enriched = enrich(chunks, mode="doc_summary", llm=llm)

        # THEN
        assert enriched[0].page_content.startswith("Method summary.")
        assert enriched[1].page_content.startswith("Getting-started summary.")
