"""Build one named collection end to end: manifest -> load -> chunk -> embed -> store.

Used only by scripts/assistant/ingest.py; the running API server never calls this.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from api.assistant.rag.chunkers import ChunkerConfig, split
from api.assistant.rag.corpus import build_manifest
from api.assistant.rag.loaders import load_source
from api.assistant.rag.models import make_embeddings
from api.assistant.rag.store import ensure_collection, make_engine, open_store
from api.config import Settings

# Owned by enrich.py once the retrieval experiments add it (raised there to the
# contracted location); declared here for now because CollectionSpec.context is
# this pull request's only consumer and enrich.py does not exist yet.
ContextMode = Literal["none", "heading_path", "llm_context", "doc_summary"]


@dataclass(frozen=True)
class CollectionSpec:
    """Which chunker, context mode, and corpus wave one named collection represents.

    :param name: The collection's table name in the assistant's vector database.
    :param chunker: Chunking strategy and size for this collection.
    :param context: Per-chunk context enrichment mode.
    :param wave: Highest corpus wave to include (see corpus.py::build_manifest).
    """

    name: str
    chunker: ChunkerConfig
    context: ContextMode
    wave: int


async def build_collection(spec: CollectionSpec, settings: Settings, repo_root: Path) -> int:
    """Build one named collection: load the corpus, chunk it, embed it, store it.

    :param spec: Which chunker/context/wave this collection represents.
    :param settings: Application settings (vector DB URL, embedding model, private
        corpus locations).
    :param repo_root: Repository root, passed through to build_manifest.
    :return: Number of chunks written to the collection.
    :raises NotImplementedError: If spec.context is not "none" (the retrieval experiments
        add enrich.py and the other three modes).
    """
    if spec.context != "none":
        raise NotImplementedError(
            f"context mode {spec.context!r} is not implemented yet; only 'none' ships "
            "in this pull request (the retrieval experiments add enrich.py and the rest)"
        )
    private_dirs = [Path(entry) for entry in settings.assistant_private_corpus_dirs]
    local_manifest = (
        Path(settings.assistant_private_corpus_manifest)
        if settings.assistant_private_corpus_manifest
        else None
    )
    sources = build_manifest(
        repo_root=repo_root,
        private_dirs=private_dirs,
        wave=spec.wave,
        local_manifest=local_manifest,
    )
    documents = [doc for source in sources for doc in load_source(source)]
    chunks = split(documents, spec.chunker)

    embeddings = make_embeddings(settings)
    vector_size = len(embeddings.embed_query("dimension probe"))
    engine = make_engine(settings.assistant_vector_db_url)
    try:
        await ensure_collection(engine, table=spec.name, vector_size=vector_size, hybrid=False)
        store = open_store(engine, table=spec.name, embeddings=embeddings)
        if chunks:
            await store.aadd_documents(chunks)
    finally:
        await engine.close()
    return len(chunks)
