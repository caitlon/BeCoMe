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


_LLM_CONTEXT_PROMPT = (
    "Document title: {title}\n\n"
    "Chunk:\n{chunk}\n\n"
    "In one short sentence, say what this chunk is about in the context of the whole "
    "document. Do not repeat the chunk's own wording verbatim; describe its role."
)


def _prepend_llm_context(chunk: Document, llm: BaseChatModel) -> Document:
    """Ask the model what this chunk is about in the document, and prepend that.

    Contextual retrieval: a short model-written sentence placed before the chunk's
    own text, so a fragment that reads as generic on its own gets the surrounding
    document's subject attached before it is embedded.

    :param chunk: The chunk to enrich.
    :param llm: The chat model asked for the context sentence.
    :return: A new Document with the model's sentence prepended.
    """
    prompt = _LLM_CONTEXT_PROMPT.format(
        title=chunk.metadata.get("title", ""), chunk=chunk.page_content
    )
    context = str(llm.invoke(prompt).content)
    return Document(
        page_content=f"{context}\n\n{chunk.page_content}", metadata=dict(chunk.metadata)
    )


_DOC_SUMMARY_PROMPT = (
    "Summarize this document in two sentences, in the document's own language:\n\n{document}"
)


def _prepend_doc_summary(chunks: list[Document], llm: BaseChatModel) -> list[Document]:
    """Prepend a short whole-document summary to every chunk from that document.

    The summary is generated once per source file - from that file's own chunks
    joined back together, the closest approximation of the original document
    available once chunking has already happened - and applied to every chunk
    sharing that "source" metadata value.

    :param chunks: Chunks to enrich, from one or more source documents.
    :param llm: The chat model asked for each document's summary.
    :return: New Documents with their source document's summary prepended.
    """
    by_source: dict[str, list[Document]] = {}
    for chunk in chunks:
        by_source.setdefault(chunk.metadata["source"], []).append(chunk)

    summaries = {
        source: str(
            llm.invoke(
                _DOC_SUMMARY_PROMPT.format(document="\n\n".join(c.page_content for c in group))
            ).content
        )
        for source, group in by_source.items()
    }
    return [
        Document(
            page_content=f"{summaries[chunk.metadata['source']]}\n\n{chunk.page_content}",
            metadata=dict(chunk.metadata),
        )
        for chunk in chunks
    ]


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
    if mode == "heading_path":
        return [_prepend_heading_path(chunk) for chunk in chunks]
    if llm is None:
        raise ValueError(f"context mode {mode!r} requires an llm")
    if mode == "llm_context":
        return [_prepend_llm_context(chunk, llm) for chunk in chunks]
    return _prepend_doc_summary(chunks, llm)
