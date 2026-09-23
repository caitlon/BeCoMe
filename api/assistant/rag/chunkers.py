"""Split loaded Documents into retrieval-sized chunks.

Only "markdown_headers" is implemented so far; the other five Strategy values
belong to the later retrieval experiments, and split() raises NotImplementedError
for them rather than silently returning something misleading.
"""

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
    :return: Retrieval-sized chunks, each with heading_path set from its section.
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
            base_metadata = {**doc.metadata, "heading_path": _heading_path(section.metadata)}
            for piece in size_splitter.split_text(section.page_content):
                chunks.append(Document(page_content=piece, metadata=dict(base_metadata)))
    return chunks


def split(
    docs: list[Document], config: ChunkerConfig, embeddings: Embeddings | None = None
) -> list[Document]:
    """Split loaded Documents into retrieval-sized chunks per config.strategy.

    :param docs: Loaded Documents (loaders.py).
    :param config: Which strategy to apply, and its size/overlap.
    :param embeddings: Only used by the future "semantic" strategy.
    :return: The resulting chunks.
    :raises NotImplementedError: For every strategy but "markdown_headers".
    """
    del embeddings  # only the future "semantic" strategy needs it
    if config.strategy == "markdown_headers":
        return _split_markdown_headers(docs, config)
    raise NotImplementedError(
        f"chunking strategy {config.strategy!r} is not implemented yet; only "
        "'markdown_headers' ships in this pull request"
    )
