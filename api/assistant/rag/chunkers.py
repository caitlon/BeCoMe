"""Split loaded Documents into retrieval-sized chunks.

Six chunking strategies, chosen by config.strategy: "markdown_headers", "fixed",
"recursive", "sentences", "semantic", and "parent_child".
"""

import math
import re
from dataclasses import dataclass
from typing import Literal

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

Strategy = Literal[
    "fixed", "recursive", "markdown_headers", "sentences", "semantic", "parent_child"
]

_HEADERS_TO_SPLIT_ON = [("#", "h1"), ("##", "h2"), ("###", "h3")]


@dataclass(frozen=True)
class ChunkerConfig:
    """Which chunking strategy to apply, and its size knobs.

    :param strategy: Which chunking strategy to run.
    :param size: Target chunk size in characters.
    :param overlap_pct: Overlap between adjacent chunks, as a percentage of size.
    """

    strategy: Strategy
    size: int = 500
    overlap_pct: int = 10


def _heading_path(metadata: dict[str, str]) -> str:
    """Join MarkdownHeaderTextSplitter's h1/h2/h3 metadata into one heading_path string.

    :param metadata: A split section's metadata (only the header levels it fell
        under are present; a header-less document yields an empty dict).
    :return: E.g. "Method > Best compromise", or "" for a header-less section.
    """
    return " > ".join(metadata[key] for key in ("h1", "h2", "h3") if key in metadata)


def _split_markdown_headers(docs: list[Document], config: ChunkerConfig) -> list[Document]:
    """Split by heading structure, then bound every resulting section's size.

    :param docs: Loaded Documents (loaders.py), each with the eight base metadata keys.
    :param config: strategy must be "markdown_headers"; size/overlap_pct bound the
        second pass.
    :return: Retrieval-sized chunks. Each chunk's heading_path is the loader's own
        heading_path (loaders.py; "" for markdown, a JSON key path for i18n) and this
        section's "#"-derived path, joined with " > " and skipping whichever side is
        empty - a markdown document keeps just its section path, an i18n document
        with no "#" lines keeps just its loader path, and a document with both gets
        the loader path first.
    """
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS_TO_SPLIT_ON, strip_headers=True
    )
    size_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.size, chunk_overlap=int(config.size * config.overlap_pct / 100)
    )
    chunks = []
    for doc in docs:
        for section in header_splitter.split_text(doc.page_content):
            heading_path = " > ".join(
                part
                for part in (doc.metadata["heading_path"], _heading_path(section.metadata))
                if part
            )
            base_metadata = {**doc.metadata, "heading_path": heading_path}
            for piece in size_splitter.split_text(section.page_content):
                chunks.append(Document(page_content=piece, metadata=dict(base_metadata)))
    return chunks


def _split_fixed(docs: list[Document], config: ChunkerConfig) -> list[Document]:
    """Cut every document into literal size-character windows.

    No word or sentence boundary is respected - this is the naive baseline every
    smarter chunking strategy is compared against in the retrieval search lab.

    :param docs: Loaded Documents.
    :param config: size is the window width; overlap_pct steps each window back by
        that percentage of size before cutting the next one.
    :return: Fixed-size chunks, in document order.
    """
    step = max(config.size - int(config.size * config.overlap_pct / 100), 1)
    chunks = []
    for doc in docs:
        text = doc.page_content
        for start in range(0, len(text), step):
            piece = text[start : start + config.size]
            if not piece:
                continue
            chunks.append(Document(page_content=piece, metadata=dict(doc.metadata)))
            if start + config.size >= len(text):
                break
    return chunks


def _split_recursive(docs: list[Document], config: ChunkerConfig) -> list[Document]:
    """Split by langchain's default separator hierarchy, size-bound only.

    No heading awareness, unlike "markdown_headers": this is the strategy the
    retrieval search lab compares against fixed-window cutting.

    :param docs: Loaded Documents.
    :param config: size/overlap_pct, passed straight to RecursiveCharacterTextSplitter.
    :return: Recursively split chunks.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.size, chunk_overlap=int(config.size * config.overlap_pct / 100)
    )
    chunks = []
    for doc in docs:
        for piece in splitter.split_text(doc.page_content):
            chunks.append(Document(page_content=piece, metadata=dict(doc.metadata)))
    return chunks


#: A sentence boundary: ".", "!", or "?" followed by whitespace and a capital letter
#: (Latin, with diacritics, including the Czech caron capitals) or digit.
#: Punctuation-based, not a full NLP tokenizer - this is a search-lab comparison
#: tool, not a production parser.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-ÞČĎĚŇŘŠŤŮŽ0-9])")


def _split_sentences(docs: list[Document], config: ChunkerConfig) -> list[Document]:
    """Group sentences greedily up to config.size characters per chunk.

    :param docs: Loaded Documents.
    :param config: size bounds each group; overlap_pct, when positive, carries the
        previous group's last sentence into the start of the next one.
    :return: Sentence-grouped chunks.
    """
    chunks = []
    for doc in docs:
        sentences = [s.strip() for s in _SENTENCE_BOUNDARY.split(doc.page_content) if s.strip()]
        groups: list[list[str]] = []
        current: list[str] = []
        current_len = 0
        for sentence in sentences:
            if current and current_len + len(sentence) + 1 > config.size:
                groups.append(current)
                current = [current[-1]] if config.overlap_pct > 0 else []
                current_len = sum(len(s) + 1 for s in current)
            current.append(sentence)
            current_len += len(sentence) + 1
        if current:
            groups.append(current)
        for group in groups:
            chunks.append(Document(page_content=" ".join(group), metadata=dict(doc.metadata)))
    return chunks


#: Break where a sentence-to-sentence jump sits above this percentile of the
#: document's OWN distance distribution - relative to how much this document's
#: meaning typically drifts between neighbors, not an absolute cutoff.
_SEMANTIC_BREAKPOINT_PERCENTILE = 95.0


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """1 - cosine similarity between two equal-length vectors, stdlib math only.

    :param a: First vector.
    :param b: Second vector.
    :return: 0.0 for identical direction, up to 2.0 for opposite direction.
    """
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - dot / (norm_a * norm_b)


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile over a small sample, stdlib math only.

    :param values: Sample of values.
    :param pct: Target percentile, 0-100.
    :return: 0.0 for an empty sample.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (pct / 100) * (len(ordered) - 1)
    lower, upper = math.floor(rank), math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _split_semantic(docs: list[Document], embeddings: Embeddings) -> list[Document]:
    """Break at the sentence boundaries whose neighbor distance is an outlier.

    :param docs: Loaded Documents.
    :param embeddings: Used to embed every sentence in a document, once per document.
    :return: Semantically grouped chunks.
    """
    chunks = []
    for doc in docs:
        sentences = [s.strip() for s in _SENTENCE_BOUNDARY.split(doc.page_content) if s.strip()]
        if len(sentences) <= 1:
            chunks.append(Document(page_content=doc.page_content, metadata=dict(doc.metadata)))
            continue
        vectors = embeddings.embed_documents(sentences)
        distances = [_cosine_distance(vectors[i], vectors[i + 1]) for i in range(len(vectors) - 1)]
        threshold = _percentile(distances, _SEMANTIC_BREAKPOINT_PERCENTILE)
        groups: list[list[str]] = [[sentences[0]]]
        for i, distance in enumerate(distances):
            if distance > threshold:
                groups.append([])
            groups[-1].append(sentences[i + 1])
        for group in groups:
            chunks.append(Document(page_content=" ".join(group), metadata=dict(doc.metadata)))
    return chunks


def _split_parent_child(docs: list[Document], config: ChunkerConfig) -> list[Document]:
    """Split into small child chunks, each carrying its larger parent's text.

    Child chunks (config.size) are the unit of embedding and matching; each keeps its
    parent chunk's full text (four times as large, a common default for this
    pattern) in metadata["parent_text"] for expanded context after retrieval.

    :param docs: Loaded Documents.
    :param config: size/overlap_pct size the CHILD chunks; the parent is 4x as large.
    :return: Child-sized chunks, each with an added "parent_text" metadata key.
    """
    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=config.size * 4, chunk_overlap=0)
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.size, chunk_overlap=int(config.size * config.overlap_pct / 100)
    )
    chunks = []
    for doc in docs:
        for parent_text in parent_splitter.split_text(doc.page_content):
            for child_text in child_splitter.split_text(parent_text):
                metadata = {**doc.metadata, "parent_text": parent_text}
                chunks.append(Document(page_content=child_text, metadata=metadata))
    return chunks


def split(
    docs: list[Document], config: ChunkerConfig, embeddings: Embeddings | None = None
) -> list[Document]:
    """Split loaded Documents into retrieval-sized chunks per config.strategy.

    :param docs: Loaded Documents (loaders.py).
    :param config: Which strategy to apply, and its size/overlap.
    :param embeddings: Used by strategy="semantic".
    :return: The resulting chunks.
    """
    if config.strategy == "markdown_headers":
        return _split_markdown_headers(docs, config)
    if config.strategy == "fixed":
        return _split_fixed(docs, config)
    if config.strategy == "recursive":
        return _split_recursive(docs, config)
    if config.strategy == "sentences":
        return _split_sentences(docs, config)
    if config.strategy == "semantic":
        if embeddings is None:
            raise ValueError("strategy='semantic' requires an embeddings client")
        return _split_semantic(docs, embeddings)
    return _split_parent_child(docs, config)
