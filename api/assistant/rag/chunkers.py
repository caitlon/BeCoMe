"""Split loaded Documents into retrieval-sized chunks.

"markdown_headers", "fixed", "recursive", and "sentences" are implemented so
far; "semantic" and "parent_child" belong to the later retrieval experiments,
and split() raises NotImplementedError for them rather than silently returning
something misleading.
"""

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


def split(
    docs: list[Document], config: ChunkerConfig, embeddings: Embeddings | None = None
) -> list[Document]:
    """Split loaded Documents into retrieval-sized chunks per config.strategy.

    :param docs: Loaded Documents (loaders.py).
    :param config: Which strategy to apply, and its size/overlap.
    :param embeddings: Only used by the future "semantic" strategy.
    :return: The resulting chunks.
    :raises NotImplementedError: For every strategy but "markdown_headers", "fixed",
        "recursive", and "sentences".
    """
    del embeddings  # only the future "semantic" strategy needs it
    if config.strategy == "markdown_headers":
        return _split_markdown_headers(docs, config)
    if config.strategy == "fixed":
        return _split_fixed(docs, config)
    if config.strategy == "recursive":
        return _split_recursive(docs, config)
    if config.strategy == "sentences":
        return _split_sentences(docs, config)
    raise NotImplementedError(f"chunking strategy {config.strategy!r} is not implemented yet")
