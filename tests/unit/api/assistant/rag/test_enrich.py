"""Unit tests for per-chunk context enrichment (fakes only, no network)."""

import hashlib

import pytest
from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from pydantic import Field

from api.assistant.rag.enrich import _DOC_SUMMARY_CHAR_BUDGET, chunk_key, enrich


class _RecordingChatModel(FakeListChatModel):
    """FakeListChatModel that also records the prompt text of every invoke() call."""

    prompts: list[str] = Field(default_factory=list)

    def _call(self, messages, stop=None, run_manager=None, **kwargs):
        self.prompts.append(messages[-1].content)
        return super()._call(messages, stop=stop, run_manager=run_manager, **kwargs)


def _chunk(
    text: str,
    heading_path: str = "",
    source: str = "docs/method-description.md",
    title: str = "Method",
) -> Document:
    """A chunk with the metadata keys enrich() reads."""
    return Document(
        page_content=text,
        metadata={
            "source": source,
            "layer": "public",
            "title": title,
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
        THEN the returned Document has the exact same text and metadata, plus
             chunk_text recording that same text
        """
        # GIVEN
        chunk = _chunk("The compromise is the midpoint of the mean and the median.")

        # WHEN
        enriched = enrich([chunk], mode="none")

        # THEN
        assert enriched[0].page_content == chunk.page_content
        assert enriched[0].metadata == {**chunk.metadata, "chunk_text": chunk.page_content}


class TestHeadingPathMode:
    """mode="heading_path" prepends the chunk's own heading trail to its text."""

    def test_prepends_the_heading_path(self):
        """
        GIVEN a chunk with a non-empty heading_path
        WHEN enrich() runs with mode="heading_path"
        THEN the heading path appears before the chunk's own text, separated by a
             blank line, and chunk_text still holds the chunk's original text
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
        assert enriched[0].metadata["chunk_text"] == chunk.page_content

    def test_leaves_a_headingless_chunk_unchanged(self):
        """
        GIVEN a chunk with an empty heading_path (a header-less document, e.g. a PDF)
        WHEN enrich() runs with mode="heading_path"
        THEN there is nothing to prepend, so the text is unchanged, and chunk_text
             still records that same text
        """
        # GIVEN
        chunk = _chunk("Plain text with no heading structure.", heading_path="")

        # WHEN
        enriched = enrich([chunk], mode="heading_path")

        # THEN
        assert enriched[0].page_content == "Plain text with no heading structure."
        assert enriched[0].metadata["chunk_text"] == chunk.page_content


class TestLlmContextMode:
    """mode="llm_context" asks the model what each chunk is about, then prepends it."""

    def test_prepends_the_models_own_context_sentence(self):
        """
        GIVEN a chunk and a fake model with a canned context sentence
        WHEN enrich() runs with mode="llm_context"
        THEN the model's sentence appears before the chunk's own text, and
             chunk_text holds the chunk's own text on its own
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
        assert enriched[0].metadata["chunk_text"] == chunk.page_content

    def test_requires_an_llm(self):
        """
        GIVEN mode="llm_context" but llm=None
        WHEN enrich() is called
        THEN it raises ValueError rather than failing deep inside llm.invoke
        """
        # GIVEN / WHEN / THEN
        with pytest.raises(ValueError, match="llm_context"):
            enrich([_chunk("text")], mode="llm_context", llm=None)

    def test_strips_a_think_block_from_the_models_reply(self):
        """
        GIVEN a fake model whose reply carries a <think>...</think> block before its
             actual context sentence
        WHEN enrich() runs with mode="llm_context"
        THEN the stored text starts with the context sentence, with no trace of the
             reasoning block
        """
        # GIVEN
        chunk = _chunk("It uses every opinion, which is its virtue and its flaw.")
        llm = FakeListChatModel(
            responses=[
                "<think>The chunk criticizes averaging.</think>\n\n"
                "Describes a weakness of the arithmetic mean."
            ]
        )

        # WHEN
        enriched = enrich([chunk], mode="llm_context", llm=llm)

        # THEN
        assert enriched[0].page_content == (
            "Describes a weakness of the arithmetic mean.\n\n"
            "It uses every opinion, which is its virtue and its flaw."
        )

    def test_keeps_a_reply_whose_think_block_never_closes(self):
        """
        GIVEN a fake model whose reply opens a <think> block and never closes it
        WHEN enrich() runs with mode="llm_context"
        THEN the reply is kept as it is, since only a complete block is removed
        """
        # GIVEN
        chunk = _chunk("It uses every opinion.")
        llm = FakeListChatModel(responses=["<think>Still reasoning about the chunk"])

        # WHEN
        enriched = enrich([chunk], mode="llm_context", llm=llm)

        # THEN
        assert enriched[0].page_content == (
            "<think>Still reasoning about the chunk\n\nIt uses every opinion."
        )


class TestDocSummaryMode:
    """mode="doc_summary" prepends one summary per source document, not per chunk."""

    def test_prepends_the_same_summary_to_every_chunk_of_one_source(self):
        """
        GIVEN two chunks from the same source and a fake model with one canned summary
        WHEN enrich() runs with mode="doc_summary"
        THEN both chunks get the SAME summary prepended, the model was called once,
             and each keeps its OWN text in chunk_text
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
        assert enriched[0].metadata["chunk_text"] == "First chunk of the method description."
        assert enriched[1].metadata["chunk_text"] == "Second chunk of the method description."

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

    def test_strips_a_think_block_from_the_models_summary(self):
        """
        GIVEN a fake model whose summary reply carries a <think>...</think> block
        WHEN enrich() runs with mode="doc_summary"
        THEN the stored text starts with the summary, with no trace of the
             reasoning block
        """
        # GIVEN
        chunk = _chunk("First chunk of the method description.")
        llm = FakeListChatModel(
            responses=[
                "<think>This document is about a compromise method.</think>\n\n"
                "A method for aggregating expert opinions."
            ]
        )

        # WHEN
        enriched = enrich([chunk], mode="doc_summary", llm=llm)

        # THEN
        assert enriched[0].page_content == (
            "A method for aggregating expert opinions.\n\nFirst chunk of the method description."
        )

    def test_bounds_the_joined_text_sent_to_the_model(self):
        """
        GIVEN one source whose chunks joined together exceed the summary input budget
        WHEN enrich() runs with mode="doc_summary"
        THEN the model is asked about only the budget's worth of characters, taken
             from the opening of the joined text
        """
        # GIVEN
        joined = "".join(f"sentence-{i:05d}. " for i in range(2000))
        chunks = [_chunk(joined)]
        llm = _RecordingChatModel(responses=["Summary."])

        # WHEN
        enrich(chunks, mode="doc_summary", llm=llm)

        # THEN
        document_part = llm.prompts[0].split("\n\n", 1)[1]
        assert len(document_part) == _DOC_SUMMARY_CHAR_BUDGET
        assert document_part == joined[:_DOC_SUMMARY_CHAR_BUDGET]


class TestCaptionsMode:
    """mode="captions" prepends a per-chunk caption, keyed by chunk_key(), and the title."""

    def test_prepends_the_title_and_caption_when_the_caption_is_found(self):
        """
        GIVEN a chunk whose title is set and whose own text has a matching caption
        WHEN enrich() runs with mode="captions"
        THEN the title and caption appear before the chunk's own text, chunk_text
             holds the chunk's own text, and the rest of the metadata is unchanged
        """
        # GIVEN
        chunk = _chunk("Chunk body", title="Doc")
        captions = {chunk_key(chunk.page_content): "What it covers."}

        # WHEN
        enriched = enrich([chunk], mode="captions", captions=captions)

        # THEN
        assert enriched[0].page_content == "Doc. What it covers.\n\nChunk body"
        assert enriched[0].metadata == {**chunk.metadata, "chunk_text": "Chunk body"}

    def test_prepends_the_title_alone_when_no_caption_matches(self):
        """
        GIVEN a chunk whose title is set but whose chunk_key has no entry in captions
        WHEN enrich() runs with mode="captions"
        THEN only the title is prepended, still followed by a blank line
        """
        # GIVEN
        chunk = _chunk("Chunk body", title="Doc")

        # WHEN
        enriched = enrich([chunk], mode="captions", captions={})

        # THEN
        assert enriched[0].page_content == "Doc.\n\nChunk body"

    def test_leaves_the_chunk_unchanged_with_no_title_and_no_caption(self):
        """
        GIVEN a chunk with neither a title nor a matching caption
        WHEN enrich() runs with mode="captions"
        THEN there is nothing to prepend, so the text is unchanged
        """
        # GIVEN
        chunk = _chunk("Chunk body", title="")

        # WHEN
        enriched = enrich([chunk], mode="captions", captions={})

        # THEN
        assert enriched[0].page_content == "Chunk body"

    def test_requires_a_captions_mapping(self):
        """
        GIVEN mode="captions" but no captions mapping
        WHEN enrich() is called
        THEN it raises ValueError naming the missing mapping rather than failing
             deep inside the lookup
        """
        # GIVEN / WHEN / THEN
        with pytest.raises(ValueError, match="'captions'"):
            enrich([_chunk("text")], mode="captions")

    def test_does_not_require_a_model(self):
        """
        GIVEN mode="captions" and no llm argument
        WHEN enrich() is called
        THEN it succeeds without a chat model, since captions are looked up rather
             than generated
        """
        # GIVEN
        chunk = _chunk("Chunk body", title="Doc")
        captions = {chunk_key(chunk.page_content): "What it covers."}

        # WHEN
        enriched = enrich([chunk], mode="captions", captions=captions, llm=None)

        # THEN
        assert enriched[0].page_content == "Doc. What it covers.\n\nChunk body"

    def test_chunk_key_is_the_sha256_hex_digest_of_the_chunks_own_text(self):
        """
        GIVEN the text "x"
        WHEN chunk_key() is called
        THEN it returns the sha256 hex digest of that text's UTF-8 bytes
        """
        # GIVEN / WHEN / THEN
        assert chunk_key("x") == hashlib.sha256(b"x").hexdigest()


class TestUnknownMode:
    """An unrecognized mode string fails loudly instead of silently running doc_summary."""

    def test_rejects_an_unknown_mode(self):
        """
        GIVEN a mode string that is not "none", "heading_path", "captions",
             "llm_context", or "doc_summary"
        WHEN enrich() is called with an llm present
        THEN it raises ValueError naming the unknown mode
        """
        # GIVEN
        llm = FakeListChatModel(responses=["should never be reached"])

        # WHEN / THEN
        with pytest.raises(ValueError, match="unknown context mode"):
            enrich([_chunk("text")], mode="not_a_real_mode", llm=llm)
