"""Tests for the source registry and the per-turn agent context."""

from unittest.mock import MagicMock

from api.assistant.agent.context import AssistantContext, SourceRegistry
from api.assistant.rag.corpus import Layer
from api.assistant.rag.retrieval import RetrievedChunk


def _chunk(
    chunk_text: str = "BeCoMe combines the mean and the median.",
    *,
    title: str = "Method description",
    section: str = "Overview",
    url: str | None = None,
    layer: Layer = "public",
    text: str | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        text=text if text is not None else chunk_text,
        title=title,
        section=section,
        url=url,
        layer=layer,
        score=0.9,
        chunk_text=chunk_text,
    )


class TestSourceRegistry:
    """Chunks get stable, one-based numbers, and repeats keep their first number."""

    def test_first_chunk_gets_number_one(self):
        """
        GIVEN an empty registry
        WHEN a chunk is added
        THEN it is numbered 1
        """
        registry = SourceRegistry()

        assert registry.add(_chunk()) == 1

    def test_numbers_increase_in_order(self):
        """
        GIVEN a registry holding one chunk
        WHEN a different chunk is added
        THEN it is numbered 2
        """
        registry = SourceRegistry()
        registry.add(_chunk("first"))

        assert registry.add(_chunk("second")) == 2

    def test_the_same_source_keeps_its_first_number(self):
        """
        GIVEN two registered chunks
        WHEN the first one is added again
        THEN it keeps number 1 and nothing new is registered
        """
        registry = SourceRegistry()
        registry.add(_chunk("repeated"))
        registry.add(_chunk("other"))

        assert registry.add(_chunk("repeated")) == 1
        assert len(registry.refs()) == 2

    def test_the_same_words_under_another_title_are_a_second_source(self):
        """
        GIVEN a registered chunk
        WHEN the same words arrive under another title
        THEN they get a new number
        """
        registry = SourceRegistry()
        registry.add(_chunk("same words", title="First"))

        assert registry.add(_chunk("same words", title="Second")) == 2

    def test_the_same_words_under_another_section_are_a_second_source(self):
        """
        GIVEN a registered chunk
        WHEN the same words arrive under another section
        THEN they get a new number
        """
        registry = SourceRegistry()
        registry.add(_chunk("same words", section="One"))

        assert registry.add(_chunk("same words", section="Two")) == 2

    def test_the_indexed_text_does_not_tell_sources_apart(self):
        """
        GIVEN two chunks with the same words but different captions in their indexed text
        WHEN both are added
        THEN they are one source
        """
        registry = SourceRegistry()
        registry.add(_chunk("words", text="Title. caption one\n\nwords"))

        assert registry.add(_chunk("words", text="Title. caption two\n\nwords")) == 1

    def test_refs_reports_the_chunk_in_registration_order(self):
        """
        GIVEN two registered chunks
        WHEN the references are built
        THEN they carry number, title, section, url and layer, in order
        """
        registry = SourceRegistry()
        registry.add(_chunk("first", url="https://becomify.app/docs"))
        registry.add(_chunk("second", title="Other", section="Deep"))

        refs = registry.refs()

        assert [ref.n for ref in refs] == [1, 2]
        assert refs[0].title == "Method description"
        assert refs[0].section == "Overview"
        assert refs[0].url == "https://becomify.app/docs"
        assert refs[0].layer == "public"
        assert refs[1].title == "Other"
        assert refs[1].section == "Deep"

    def test_refs_of_a_local_chunk_exposes_no_path(self):
        """
        GIVEN a local-layer chunk whose url holds a filesystem path
        WHEN the references are built
        THEN the reference keeps the layer but carries no url
        """
        registry = SourceRegistry()
        registry.add(_chunk(layer="local", url="/Users/someone/private/book.pdf"))

        ref = registry.refs()[0]

        assert ref.layer == "local"
        assert ref.url is None
        assert "/Users/" not in ref.model_dump_json()

    def test_texts_returns_the_chunk_words_only(self):
        """
        GIVEN chunks whose indexed text carries a title and caption
        WHEN the texts are read
        THEN only the chunk's own words come back, with no marker or title
        """
        registry = SourceRegistry()
        registry.add(_chunk("alpha", text="Title. caption\n\nalpha"))
        registry.add(_chunk("beta", title="Other title"))

        assert registry.texts() == ["alpha", "beta"]


class TestAssistantContext:
    """The context is a plain, mutable bag the tools append to as they run."""

    def test_tool_outputs_starts_empty_and_is_mutable(self):
        """
        GIVEN a fresh context
        WHEN a tool appends its output
        THEN the output is kept
        """
        ctx = AssistantContext(
            client=MagicMock(),
            retriever=MagicMock(),
            sources=SourceRegistry(),
            tool_outputs=[],
            current_project_id=None,
            locale="en",
        )

        ctx.tool_outputs.append("<docs>...</docs>")

        assert ctx.tool_outputs == ["<docs>...</docs>"]
