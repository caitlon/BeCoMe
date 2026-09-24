"""Unit tests for chunking loaded Documents (fakes only, no network)."""

import dataclasses
import json
import math

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding, Embeddings

from api.assistant.rag.chunkers import ChunkerConfig, split
from api.assistant.rag.corpus import CorpusSource
from api.assistant.rag.loaders import load_source


def _doc(text: str, heading_path: str = "") -> Document:
    """A Document with the eight base metadata keys loaders.py always sets.

    :param text: The document's page content.
    :param heading_path: The loader-set heading_path - "" (markdown's default) unless
        given, e.g. an i18n JSON key path.
    """
    return Document(
        page_content=text,
        metadata={
            "source": "docs/method-description.md",
            "layer": "public",
            "title": "Method",
            "lang": "en",
            "url": None,
            "sha256": "abc123",
            "heading_path": heading_path,
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

    def test_keeps_the_loaders_heading_path_when_the_text_has_no_markdown_headings(self):
        """
        GIVEN an i18n-style Document whose loader set heading_path to a JSON key path,
             with no "#"-prefixed lines in its text
        WHEN split() runs with markdown_headers
        THEN the chunk keeps that heading_path, rather than losing it to the
             splitter's own (empty) header metadata
        """
        # GIVEN
        text = "Title: Creating A Project\nStep1: Sign up."
        doc = _doc(text, heading_path="gettingStarted > createProject")
        config = ChunkerConfig(strategy="markdown_headers", size=500, overlap_pct=10)

        # WHEN
        chunks = split([doc], config)

        # THEN
        assert len(chunks) == 1
        assert chunks[0].metadata["heading_path"] == "gettingStarted > createProject"

    def test_joins_the_loaders_heading_path_with_the_splitters_own(self):
        """
        GIVEN a Document whose loader set a heading_path AND whose text has its own
             "#"-prefixed heading
        WHEN split() runs with markdown_headers
        THEN the chunk's heading_path is the loader's path and the splitter's path
             joined with " > ", loader path first
        """
        # GIVEN
        text = "## Best compromise\n\nIt is the midpoint of the mean and the median.\n"
        doc = _doc(text, heading_path="gettingStarted")
        config = ChunkerConfig(strategy="markdown_headers", size=500, overlap_pct=10)

        # WHEN
        chunks = split([doc], config)

        # THEN
        assert len(chunks) == 1
        assert chunks[0].metadata["heading_path"] == "gettingStarted > Best compromise"


class TestFixedStrategy:
    """The naive baseline: literal size-character windows, no boundary awareness."""

    def test_cuts_literal_windows_with_no_overlap(self):
        """
        GIVEN a 25-character document and size=10, overlap_pct=0
        WHEN split() runs with strategy="fixed"
        THEN it produces three windows of 10, 10, and 5 characters
        """
        # GIVEN
        text = "abcdefghijklmnopqrstuvwxy"  # 25 characters
        config = ChunkerConfig(strategy="fixed", size=10, overlap_pct=0)

        # WHEN
        chunks = split([_doc(text)], config)

        # THEN
        assert [c.page_content for c in chunks] == ["abcdefghij", "klmnopqrst", "uvwxy"]

    def test_overlap_repeats_the_tail_of_the_previous_window(self):
        """
        GIVEN the same document with size=10, overlap_pct=20 (2-character step back)
        WHEN split() runs
        THEN each window after the first starts 2 characters before the previous one ended
        """
        # GIVEN
        text = "abcdefghijklmnopqrstuvwxy"
        config = ChunkerConfig(strategy="fixed", size=10, overlap_pct=20)

        # WHEN
        chunks = split([_doc(text)], config)

        # THEN
        assert [c.page_content for c in chunks] == ["abcdefghij", "ijklmnopqr", "qrstuvwxy"]


class TestRecursiveStrategy:
    """Splits by langchain's default separator hierarchy, with no heading awareness."""

    def test_prefers_paragraph_boundaries_over_mid_word_cuts(self):
        """
        GIVEN two short paragraphs that together exceed size
        WHEN split() runs with strategy="recursive"
        THEN the split falls on the paragraph boundary, not mid-word
        """
        # GIVEN
        text = "First short paragraph here.\n\nSecond short paragraph there."
        config = ChunkerConfig(strategy="recursive", size=30, overlap_pct=0)

        # WHEN
        chunks = split([_doc(text)], config)

        # THEN
        assert chunks[0].page_content == "First short paragraph here."
        assert chunks[1].page_content == "Second short paragraph there."
        assert all(c.metadata["source"] == "docs/method-description.md" for c in chunks)


class TestSentencesStrategy:
    """Groups sentences greedily up to config.size, punctuation-based boundaries."""

    _TEXT = (
        "BeCoMe combines the mean and the median. It reports a maximum error too. "
        "Widening a range does not move the center. This is the third fact worth knowing."
    )

    def test_groups_sentences_without_overlap(self):
        """
        GIVEN four sentences and size=80, overlap_pct=0
        WHEN split() runs with strategy="sentences"
        THEN sentences 1-2 group together (fits in 80), then 3 and 4 are each alone
        """
        # GIVEN
        config = ChunkerConfig(strategy="sentences", size=80, overlap_pct=0)

        # WHEN
        chunks = split([_doc(self._TEXT)], config)

        # THEN
        assert [c.page_content for c in chunks] == [
            "BeCoMe combines the mean and the median. It reports a maximum error too.",
            "Widening a range does not move the center.",
            "This is the third fact worth knowing.",
        ]

    def test_overlap_carries_the_last_sentence_into_the_next_group(self):
        """
        GIVEN the same four sentences, size=80, overlap_pct=10 (any positive value)
        WHEN split() runs
        THEN each group after the first repeats the previous group's last sentence
        """
        # GIVEN
        config = ChunkerConfig(strategy="sentences", size=80, overlap_pct=10)

        # WHEN
        chunks = split([_doc(self._TEXT)], config)

        # THEN
        assert [c.page_content for c in chunks] == [
            "BeCoMe combines the mean and the median. It reports a maximum error too.",
            "It reports a maximum error too. Widening a range does not move the center.",
            "Widening a range does not move the center. This is the third fact worth knowing.",
        ]

    def test_treats_a_czech_caron_capital_as_a_sentence_start(self):
        """
        GIVEN two Czech sentences, the second starting with a caron capital ("Skoda")
        WHEN split() runs with strategy="sentences" and a size that fits either
             sentence alone but not both together
        THEN the caron capital is recognized as a sentence start, so the two
             sentences land in separate chunks
        """
        # GIVEN
        text = "Odborníci hodnotí projekt. Škoda vznikla při zpoždění."
        config = ChunkerConfig(strategy="sentences", size=30, overlap_pct=0)

        # WHEN
        chunks = split([_doc(text)], config)

        # THEN
        assert [c.page_content for c in chunks] == [
            "Odborníci hodnotí projekt.",
            "Škoda vznikla při zpoždění.",
        ]


def _unit_vector(angle_degrees: float) -> list[float]:
    """A 2D unit vector at the given angle, for placing fake sentence embeddings by hand.

    :param angle_degrees: Angle from the positive x axis, in degrees.
    :return: [cos, sin] of that angle.
    """
    radians = math.radians(angle_degrees)
    return [math.cos(radians), math.sin(radians)]


class _FixedVectorEmbeddings(Embeddings):
    """A minimal Embeddings stub: every known sentence maps to one fixed vector.

    Lets a test place sentences at chosen angles and get exact, predictable neighbor
    cosine distances, rather than relying on a hash-based fake embedding.
    """

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        """
        :param vectors: Exact sentence text mapped to its fixed embedding vector.
        """
        self._vectors = vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors[text] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vectors[text]


class TestSemanticStrategy:
    """An in-house semantic breakpoint: percentile of neighbor cosine distance."""

    def test_breaks_where_neighboring_sentences_stop_repeating(self):
        """
        GIVEN six sentences: three identical ones, then three different identical ones
        WHEN split() runs with strategy="semantic" and a real embeddings client
        THEN it breaks exactly once, at the boundary between the two repeated texts
        """
        # GIVEN
        text = " ".join(["X sentence one."] * 3 + ["Y sentence two."] * 3)
        config = ChunkerConfig(strategy="semantic")
        embeddings = DeterministicFakeEmbedding(size=16)

        # WHEN
        chunks = split([_doc(text)], config, embeddings=embeddings)

        # THEN
        assert len(chunks) == 2
        assert chunks[0].page_content == "X sentence one. X sentence one. X sentence one."
        assert chunks[1].page_content == "Y sentence two. Y sentence two. Y sentence two."

    def test_a_single_sentence_document_becomes_one_chunk(self):
        """
        GIVEN a document with no sentence boundary at all
        WHEN split() runs with strategy="semantic"
        THEN it is returned as a single chunk, unchanged, since there is nothing to compare
        """
        # GIVEN
        config = ChunkerConfig(strategy="semantic")
        embeddings = DeterministicFakeEmbedding(size=16)

        # WHEN
        chunks = split([_doc("Just one sentence, no boundary")], config, embeddings=embeddings)

        # THEN
        assert len(chunks) == 1
        assert chunks[0].page_content == "Just one sentence, no boundary"

    def test_requires_an_embeddings_client(self):
        """
        GIVEN strategy="semantic" but embeddings=None
        WHEN split() is called
        THEN it raises ValueError rather than failing deep inside embed_documents
        """
        config = ChunkerConfig(strategy="semantic")

        with pytest.raises(ValueError, match="embeddings"):
            split([_doc("some text")], config, embeddings=None)

    def test_a_coherent_paragraph_still_breaks_at_its_largest_relative_jump(self):
        """
        GIVEN four sentences placed a few degrees apart on the unit circle, so every
             neighbor distance is small, and one gap only a little larger than the rest
        WHEN split() runs with strategy="semantic"
        THEN it still breaks exactly once, at that largest gap, since the threshold is
             relative to this document's own distances rather than an absolute floor,
             so a paragraph that never truly changes topic still gets cut
        """
        # GIVEN
        sentences = [
            "Alpha sentence one.",
            "Beta sentence two.",
            "Gamma sentence three.",
            "Delta sentence four.",
        ]
        angles_degrees = [0.0, 3.0, 6.0, 10.0]
        vectors = {
            sentence: _unit_vector(angle)
            for sentence, angle in zip(sentences, angles_degrees, strict=True)
        }
        text = " ".join(sentences)
        config = ChunkerConfig(strategy="semantic")
        embeddings = _FixedVectorEmbeddings(vectors)

        # WHEN
        chunks = split([_doc(text)], config, embeddings=embeddings)

        # THEN
        assert [c.page_content for c in chunks] == [
            "Alpha sentence one. Beta sentence two. Gamma sentence three.",
            "Delta sentence four.",
        ]

    def test_a_two_sentence_document_stays_one_chunk_even_at_the_maximum_distance(self):
        """
        GIVEN two sentences placed at opposite points on the unit circle, the largest
             cosine distance two vectors can have
        WHEN split() runs with strategy="semantic"
        THEN it still stays a single chunk, because with only one neighbor distance,
             that distance is its own 95th percentile, and a distance is never
             strictly greater than itself
        """
        # GIVEN
        sentences = ["Alpha sentence one.", "Beta sentence two."]
        vectors = {
            sentences[0]: _unit_vector(0.0),
            sentences[1]: _unit_vector(180.0),
        }
        text = " ".join(sentences)
        config = ChunkerConfig(strategy="semantic")
        embeddings = _FixedVectorEmbeddings(vectors)

        # WHEN
        chunks = split([_doc(text)], config, embeddings=embeddings)

        # THEN
        assert len(chunks) == 1
        assert chunks[0].page_content == text


class TestParentChildStrategy:
    """Small child chunks for matching, each carrying its larger parent as context."""

    def test_child_chunks_carry_their_parent_text_in_metadata(self):
        """
        GIVEN a short document that is one parent split into three children
        WHEN split() runs with strategy="parent_child"
        THEN every child chunk's metadata carries the SAME parent_text, the whole
             original document, since it fit in one parent-sized piece
        """
        # GIVEN
        text = "BeCoMe averages the mean and the median values."
        config = ChunkerConfig(strategy="parent_child", size=20, overlap_pct=0)

        # WHEN
        chunks = split([_doc(text)], config)

        # THEN
        assert [c.page_content for c in chunks] == [
            "BeCoMe averages the",
            "mean and the median",
            "values.",
        ]
        assert all(c.metadata["parent_text"] == text for c in chunks)
        assert all(c.metadata["source"] == "docs/method-description.md" for c in chunks)


class TestUnknownStrategy:
    """split() fails loudly for a strategy value none of its branches handle."""

    def test_raises_value_error(self):
        """
        GIVEN a ChunkerConfig naming a strategy split() does not recognize
        WHEN split() is called
        THEN it raises ValueError rather than silently treating it as parent_child
        """
        # GIVEN
        config = ChunkerConfig(strategy="unknown")  # type: ignore[arg-type]

        # WHEN / THEN
        with pytest.raises(ValueError, match="unknown"):
            split([_doc("text")], config)


class TestLoaderChunkerIntegration:
    """End-to-end: loaders.load_source's heading_path must survive split()."""

    def test_i18n_json_chunks_keep_their_sections_key_path_as_heading_path(self, tmp_path):
        """
        GIVEN a small nested i18n JSON file loaded through loaders.load_source
        WHEN its Documents are split with markdown_headers
        THEN every chunk's heading_path is non-empty and equals its own section's
             key path - i18n text has no "#" lines to derive one from otherwise
        """
        # GIVEN
        data = {
            "gettingStarted": {
                "title": "Getting Started",
                "createProject": {
                    "title": "Creating a Project",
                    "step1": "Sign up.",
                },
            },
        }
        json_path = tmp_path / "frontend" / "src" / "i18n" / "locales" / "en" / "docs.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(data), encoding="utf-8")
        source = CorpusSource(
            path=json_path,
            layer="public",
            kind="i18n_json",
            title="Documentation",
            lang="en",
            url=None,
            wave=1,
        )
        documents = load_source(source)
        config = ChunkerConfig(strategy="markdown_headers", size=500, overlap_pct=10)

        # WHEN
        chunks = split(documents, config)

        # THEN
        assert len(chunks) == len(documents)
        for document, chunk in zip(documents, chunks, strict=True):
            assert chunk.metadata["heading_path"] != ""
            assert chunk.metadata["heading_path"] == document.metadata["heading_path"]
