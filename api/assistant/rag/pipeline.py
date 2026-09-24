"""Build one named collection end to end: manifest -> load -> chunk -> embed -> store.

Used only by scripts/assistant/ingest.py; the running API server never calls this.
"""

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import psycopg
from langchain_core.documents import Document

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


def _corpus_hash(chunks: list[Document]) -> str:
    """Hash a chunk set for change detection: same content in, same hash out.

    :param chunks: The chunks about to be written to a collection.
    :return: One hex digest over every chunk's own sha256 (loaders.py), sorted so the
        result does not depend on load order.
    """
    combined = "".join(sorted(chunk.metadata["sha256"] for chunk in chunks))
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def git_version(repo_dir: Path) -> str | None:
    """Name the commit a git repository is checked out at, for the build registry.

    :param repo_dir: The repository's root: the BeCoMe checkout, or the private corpus
        repository that holds the local manifest.
    :return: `git describe --tags --always --dirty` output such as "wave-1",
        "wave-1-2-g1a2b3c4" or "1a2b3c4-dirty"; None when git is not installed or
        repo_dir is not itself a repository root. Without that check, a plain folder
        inside the BeCoMe checkout would report BeCoMe's commit as the corpus version.
    """
    git = shutil.which("git")
    if git is None or not (repo_dir / ".git").exists():
        return None
    # S603 is safe here: git's own resolved path and fixed flags, no shell.
    result = subprocess.run(  # noqa: S603
        [git, "-C", str(repo_dir), "describe", "--tags", "--always", "--dirty"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


async def _record_collection(
    vector_db_url: str,
    spec: CollectionSpec,
    embedding_model: str,
    corpus_hash: str,
    chunk_count: int,
    app_version: str | None,
    corpus_version: str | None,
) -> None:
    """Upsert one collection's build metadata into the assistant_collections registry.

    Creates the registry table on first use. Never touched by Alembic: it lives in
    the assistant's own database, entirely separate from the application's.

    :param vector_db_url: Settings.assistant_vector_db_url.
    :param spec: The collection's chunker/context/wave.
    :param embedding_model: Which embedding model produced these vectors.
    :param corpus_hash: _corpus_hash() of the chunks just written.
    :param chunk_count: How many chunks this build wrote.
    :param app_version: git_version() of the BeCoMe checkout, or None.
    :param corpus_version: git_version() of the private corpus repository, or None
        when there is no local layer or it is not a repository.
    """
    dsn = vector_db_url.replace("postgresql+psycopg://", "postgresql://")
    async with await psycopg.AsyncConnection.connect(dsn) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assistant_collections (
                name TEXT PRIMARY KEY,
                chunker_strategy TEXT NOT NULL,
                chunk_size INTEGER NOT NULL,
                overlap_pct INTEGER NOT NULL,
                context_mode TEXT NOT NULL,
                wave INTEGER NOT NULL,
                embedding_model TEXT NOT NULL,
                corpus_hash TEXT NOT NULL,
                chunk_count INTEGER NOT NULL,
                app_version TEXT,
                corpus_version TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        await conn.execute(
            """
            INSERT INTO assistant_collections
                (name, chunker_strategy, chunk_size, overlap_pct, context_mode, wave,
                 embedding_model, corpus_hash, chunk_count, app_version, corpus_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                chunker_strategy = EXCLUDED.chunker_strategy,
                chunk_size = EXCLUDED.chunk_size,
                overlap_pct = EXCLUDED.overlap_pct,
                context_mode = EXCLUDED.context_mode,
                wave = EXCLUDED.wave,
                embedding_model = EXCLUDED.embedding_model,
                corpus_hash = EXCLUDED.corpus_hash,
                chunk_count = EXCLUDED.chunk_count,
                app_version = EXCLUDED.app_version,
                corpus_version = EXCLUDED.corpus_version,
                created_at = now()
            """,
            (
                spec.name,
                spec.chunker.strategy,
                spec.chunker.size,
                spec.chunker.overlap_pct,
                spec.context,
                spec.wave,
                embedding_model,
                corpus_hash,
                chunk_count,
                app_version,
                corpus_version,
            ),
        )
        await conn.commit()


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
    # Read before loading, so the registry names exactly the versions this build read.
    # An absolute manifest path wins the join, the same way corpus.py resolves it.
    app_version = git_version(repo_root)
    corpus_version = git_version((repo_root / local_manifest).parent) if local_manifest else None
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
    await _record_collection(
        settings.assistant_vector_db_url,
        spec,
        embedding_model=settings.assistant_embedding_model,
        corpus_hash=_corpus_hash(chunks),
        chunk_count=len(chunks),
        app_version=app_version,
        corpus_version=corpus_version,
    )
    return len(chunks)
