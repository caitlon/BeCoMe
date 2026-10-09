"""Tests for the source registry and the per-turn agent context."""

from api.assistant.agent.context import SNIPPET_CHARS, SourceRegistry, _excerpt
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

    def test_refs_carries_a_snippet_of_the_passage(self):
        """
        GIVEN a public chunk and a local chunk, one of them with untidy whitespace
        WHEN the references are built
        THEN each carries the first words of its passage as a tidy snippet
        """
        registry = SourceRegistry()
        registry.add(_chunk("The mean\nand the   median."))
        registry.add(_chunk("Private words.", layer="local"))

        refs = registry.refs()

        assert refs[0].snippet == "The mean and the median."
        assert refs[1].snippet == "Private words."

    def test_refs_cuts_a_long_passage_to_the_snippet_limit(self):
        """
        GIVEN a chunk much longer than the snippet limit
        WHEN the references are built
        THEN the snippet fits the limit and ends with an ellipsis
        """
        registry = SourceRegistry()
        registry.add(_chunk("word " * 200))

        snippet = registry.refs()[0].snippet

        assert len(snippet) <= SNIPPET_CHARS
        assert snippet.endswith("\u2026")

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

    def test_texts_returns_what_the_model_is_shown_except_the_marker(self):
        """
        GIVEN chunks whose indexed text carries a generated caption
        WHEN the texts are read
        THEN each chunk gives its title, its section and its own words as separate
            strings, with no marker and no caption
        """
        registry = SourceRegistry()
        registry.add(_chunk("alpha", text="Title. caption\n\nalpha", title="Guide 2024"))
        registry.add(_chunk("beta", title="Other title", section="Deep"))

        assert registry.texts() == [
            "Guide 2024",
            "Overview",
            "alpha",
            "Other title",
            "Deep",
            "beta",
        ]

    def test_texts_leaves_out_an_empty_section(self):
        """
        GIVEN a chunk with no section
        WHEN the texts are read
        THEN the title and the words come back, and no empty string
        """
        registry = SourceRegistry()
        registry.add(_chunk("alpha", section=""))

        assert registry.texts() == ["Method description", "alpha"]

    def test_texts_lets_a_year_in_a_title_ground_the_repeated_year(self):
        """
        GIVEN a source whose title holds a year
        WHEN the texts are read
        THEN the year is among them
        """
        registry = SourceRegistry()
        registry.add(_chunk("words", title="Report 2021"))

        assert any("2021" in text for text in registry.texts())

    def test_numbered_pairs_every_chunk_with_its_number_in_registration_order(self):
        """
        GIVEN two registered chunks and a repeat of the first
        WHEN the numbered chunks are read
        THEN each registered chunk appears once with the number it was given, and the
            repeat adds nothing
        """
        registry = SourceRegistry()
        first, second = _chunk("first"), _chunk("second", title="Other")
        registry.add(first)
        registry.add(second)
        registry.add(first)

        assert registry.numbered() == [(1, first), (2, second)]

    def test_numbered_of_an_empty_registry_is_empty(self):
        """
        GIVEN an empty registry
        WHEN the numbered chunks are read
        THEN the list is empty
        """
        assert SourceRegistry().numbered() == []


class TestExcerpt:
    """The snippet is plain text on one line, cut at a word and marked with an ellipsis."""

    def test_collapses_whitespace_runs_to_one_space(self):
        """
        GIVEN text with newlines, tabs and repeated spaces
        WHEN the excerpt is made
        THEN every run becomes a single space and the ends are trimmed
        """
        assert _excerpt("  one\n\ntwo\t three   four ") == "one two three four"

    def test_strips_control_characters(self):
        """
        GIVEN text holding a null byte, an escape and a zero-width space
        WHEN the excerpt is made
        THEN those characters are gone and the words stay
        """
        assert _excerpt("al\x00pha\x1b[0m be\u200bta") == "alpha[0m beta"

    def test_leaves_short_text_untouched(self):
        """
        GIVEN text no longer than the limit
        WHEN the excerpt is made
        THEN it comes back without an ellipsis
        """
        assert _excerpt("short text", limit=10) == "short text"

    def test_cuts_at_the_last_space_before_the_limit(self):
        """
        GIVEN text longer than the limit
        WHEN the excerpt is made
        THEN it is cut at the last space before the limit and ends with an ellipsis
        """
        assert _excerpt("alpha beta gamma", limit=12) == "alpha beta\u2026"

    def test_cuts_at_the_limit_when_there_is_no_space(self):
        """
        GIVEN one long word
        WHEN the excerpt is made
        THEN it is cut so that the text and its ellipsis fit the limit exactly
        """
        assert _excerpt("abcdefghij", limit=5) == "abcd\u2026"

    def test_the_default_limit_is_the_snippet_length(self):
        """
        GIVEN text one character over the default limit
        WHEN the excerpt is made without a limit
        THEN it is shortened, and text at exactly the limit is not
        """
        assert _excerpt("a" * SNIPPET_CHARS) == "a" * SNIPPET_CHARS
        assert _excerpt("a" * (SNIPPET_CHARS + 1)).endswith("\u2026")
