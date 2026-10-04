"""Add per-chunk context before embedding: the retrieval lab's context factor.

enrich() returns NEW Documents; the chunk's own metadata (including provenance) is
carried over unchanged except for one addition. Every enriched Document also carries
metadata["chunk_text"], the chunk's own text before enrichment, for every mode
including "none", so a later citation or a source-grounding check can tell the
chunk's own text apart from any model-written text fused into page_content.

Mode "captions" does not generate anything locally: its captions are written outside
this stack, kept in a file in the private corpus repository, and keyed by chunk_key()
on the chunk's own text as split (before enrichment). A chunk whose key has no entry
in that mapping still gets its title prepended on its own.
"""

import hashlib
from collections.abc import Mapping
from typing import Literal

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel

from api.assistant.rag.models import strip_think_block

ContextMode = Literal["none", "heading_path", "llm_context", "doc_summary", "captions"]


def chunk_key(text: str) -> str:
    """The key a chunk's caption is stored under: the sha256 hex digest of its own text.

    Two chunks with identical text share a key, and so share a caption.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _prepend_caption(chunk: Document, captions: Mapping[str, str]) -> Document:
    """Prepend the chunk's own title and its looked-up caption to its text.

    The caption comes from outside this module (see the module docstring); a chunk
    whose chunk_key has no entry in captions falls back to the title on its own.

    :param chunk: The chunk to enrich.
    :param captions: chunk_key(chunk's own text) -> caption.
    :return: A new Document; text is unchanged when there is neither a title nor a
        matching caption.
    """
    title = chunk.metadata.get("title", "")
    caption = captions.get(chunk_key(chunk.page_content), "")
    context = " ".join(part for part in (f"{title}." if title else "", caption) if part)
    text = f"{context}\n\n{chunk.page_content}" if context else chunk.page_content
    return Document(
        page_content=text, metadata={**chunk.metadata, "chunk_text": chunk.page_content}
    )


def _prepend_heading_path(chunk: Document) -> Document:
    """Prepend the chunk's own heading_path metadata to its text.

    :param chunk: The chunk to enrich.
    :return: A new Document; text is unchanged when heading_path is empty.
    """
    heading_path = chunk.metadata.get("heading_path", "")
    text = f"{heading_path}\n\n{chunk.page_content}" if heading_path else chunk.page_content
    return Document(
        page_content=text, metadata={**chunk.metadata, "chunk_text": chunk.page_content}
    )


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

    The model runs at temperature 0, so rebuilding the same corpus writes the same text.

    :param chunk: The chunk to enrich.
    :param llm: The chat model asked for the context sentence.
    :return: A new Document with the model's sentence prepended.
    """
    prompt = _LLM_CONTEXT_PROMPT.format(
        title=chunk.metadata.get("title", ""), chunk=chunk.page_content
    )
    context = strip_think_block(str(llm.bind(temperature=0).invoke(prompt).content))
    return Document(
        page_content=f"{context}\n\n{chunk.page_content}",
        metadata={**chunk.metadata, "chunk_text": chunk.page_content},
    )


_DOC_SUMMARY_PROMPT = (
    "Summarize this document in two sentences, in the document's own language:\n\n{document}"
)

# Kept well under the chat llama-server's 16384-token context window
# (scripts/assistant/run-llama-servers.sh), even at a conservative ~3 characters per
# token. 24_000 characters is about 8_000 tokens, leaving headroom for the prompt
# template and the model's own reply, so joining one source's chunks can never
# overflow the context window the way an unbounded join could for a large PDF.
_DOC_SUMMARY_CHAR_BUDGET = 24_000


def _prepend_doc_summary(chunks: list[Document], llm: BaseChatModel) -> list[Document]:
    """Prepend a short whole-document summary to every chunk from that document.

    The summary is generated once per source file, from that file's own chunks
    joined back together. This is the closest approximation of the original document
    available once chunking has already happened, applied to every chunk sharing that
    "source" metadata value. Only the opening _DOC_SUMMARY_CHAR_BUDGET characters of
    that joined text are sent to the model, so the summary reads the opening of a
    long document rather than all of it.

    The model runs at temperature 0, so rebuilding the same corpus writes the same text.

    :param chunks: Chunks to enrich, from one or more source documents.
    :param llm: The chat model asked for each document's summary.
    :return: New Documents with their source document's summary prepended.
    """
    by_source: dict[str, list[Document]] = {}
    for chunk in chunks:
        by_source.setdefault(chunk.metadata["source"], []).append(chunk)

    bound_llm = llm.bind(temperature=0)
    summaries = {
        source: strip_think_block(
            str(
                bound_llm.invoke(
                    _DOC_SUMMARY_PROMPT.format(
                        document="\n\n".join(c.page_content for c in group)[
                            :_DOC_SUMMARY_CHAR_BUDGET
                        ]
                    )
                ).content
            )
        )
        for source, group in by_source.items()
    }
    return [
        Document(
            page_content=f"{summaries[chunk.metadata['source']]}\n\n{chunk.page_content}",
            metadata={**chunk.metadata, "chunk_text": chunk.page_content},
        )
        for chunk in chunks
    ]


def enrich(
    chunks: list[Document],
    mode: ContextMode,
    llm: BaseChatModel | None = None,
    captions: Mapping[str, str] | None = None,
) -> list[Document]:
    """Prepend context to each chunk's text before it is embedded and stored.

    :param chunks: Chunks to enrich (chunkers.split()'s output).
    :param mode: Which context to add.
    :param llm: Required for "llm_context" and "doc_summary"; ignored by "none",
        "heading_path", and "captions".
    :param captions: Required for "captions": chunk_key(chunk's own text) -> caption,
        written outside this module (see the module docstring). Ignored by every
        other mode.
    :return: New Documents with the same metadata and mode-appropriate content.
    :raises ValueError: If mode is "captions" and captions is None, if mode needs an
        llm and none was given, or mode is not one of "none", "heading_path",
        "captions", "llm_context", "doc_summary".
    """
    if mode == "none":
        return [
            Document(
                page_content=c.page_content, metadata={**c.metadata, "chunk_text": c.page_content}
            )
            for c in chunks
        ]
    if mode == "heading_path":
        return [_prepend_heading_path(chunk) for chunk in chunks]
    if mode == "captions":
        if captions is None:
            raise ValueError("context mode 'captions' requires a captions mapping")
        return [_prepend_caption(chunk, captions) for chunk in chunks]
    if llm is None:
        raise ValueError(f"context mode {mode!r} requires an llm")
    if mode == "llm_context":
        return [_prepend_llm_context(chunk, llm) for chunk in chunks]
    if mode == "doc_summary":
        return _prepend_doc_summary(chunks, llm)
    raise ValueError(f"unknown context mode {mode!r}")
