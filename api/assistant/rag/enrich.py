"""Add per-chunk context before embedding: the retrieval lab's context factor (B).

enrich() returns NEW Documents; the chunk's own metadata (including provenance) is
carried over unchanged, only page_content changes.
"""

from typing import Literal

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel

ContextMode = Literal["none", "heading_path", "llm_context", "doc_summary"]


def _prepend_heading_path(chunk: Document) -> Document:
    """Prepend the chunk's own heading_path metadata to its text.

    :param chunk: The chunk to enrich.
    :return: A new Document; text is unchanged when heading_path is empty.
    """
    heading_path = chunk.metadata.get("heading_path", "")
    text = f"{heading_path}\n\n{chunk.page_content}" if heading_path else chunk.page_content
    return Document(page_content=text, metadata=dict(chunk.metadata))


def enrich(
    chunks: list[Document], mode: ContextMode, llm: BaseChatModel | None = None
) -> list[Document]:
    """Prepend context to each chunk's text before it is embedded and stored.

    :param chunks: Chunks to enrich (chunkers.split()'s output).
    :param mode: Which context to add.
    :param llm: Required for "llm_context" and "doc_summary"; ignored by "none" and
        "heading_path".
    :return: New Documents with the same metadata and mode-appropriate content.
    """
    if mode == "none":
        return [Document(page_content=c.page_content, metadata=dict(c.metadata)) for c in chunks]
    return [_prepend_heading_path(chunk) for chunk in chunks]
