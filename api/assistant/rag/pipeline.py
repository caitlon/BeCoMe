"""Build one named collection end to end: manifest -> load -> chunk -> embed -> store.

Used only by scripts/assistant/ingest.py; the running API server never calls this.
"""

import hashlib
import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import psycopg
from langchain_core.documents import Document

from api.assistant.rag.chunkers import ChunkerConfig, split
from api.assistant.rag.corpus import build_manifest
from api.assistant.rag.enrich import ContextMode, chunk_key, enrich
from api.assistant.rag.loaders import load_source
from api.assistant.rag.models import make_chat_model, make_embeddings
from api.assistant.rag.store import (
    create_collection,
    make_engine,
    open_store,
    staging_table,
    swap_in_staging,
)
from api.config import Settings

logger = logging.getLogger(__name__)


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


async def _publish_collection(
    vector_db_url: str,
    spec: CollectionSpec,
    embedding_model: str,
    corpus_hash: str,
    chunk_count: int,
    app_version: str | None,
    corpus_version: str | None,
) -> None:
    """Swap the freshly built staging table live and upsert its registry row.

    Both happen in this one connection's transaction, committed together at the end:
    swap_in_staging's DDL and the registry upsert either both take effect or neither
    does, so a reader never finds a table the assistant_collections registry does not
    describe. Creates the registry table on first use. Never touched by Alembic: it
    lives in the assistant's own database, entirely separate from the application's.

    :param vector_db_url: Settings.assistant_vector_db_url.
    :param spec: The collection's chunker/context/wave; spec.name is the collection
        going live, staging_table(spec.name) its already-built staging table.
    :param embedding_model: Which embedding model produced these vectors.
    :param corpus_hash: _corpus_hash() of the chunks just written.
    :param chunk_count: How many chunks this build wrote.
    :param app_version: git_version() of the BeCoMe checkout, or None.
    :param corpus_version: git_version() of the private corpus repository, or None
        when there is no local layer or it is not a repository.
    """
    dsn = vector_db_url.replace("postgresql+psycopg://", "postgresql://")
    async with await psycopg.AsyncConnection.connect(dsn) as conn:
        await swap_in_staging(conn, spec.name)
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


def load_captions(settings: Settings, repo_root: Path) -> dict[str, str]:
    """Load the chunk_key -> caption mapping the "captions" context mode reads.

    The file is written outside this stack (see enrich.py's module docstring) and
    kept in the private corpus repository, next to the local manifest.

    :param settings: Application settings; assistant_captions_file names the file.
    :param repo_root: Repository root; a relative assistant_captions_file resolves
        from here, the same way assistant_private_corpus_manifest does - an
        absolute path wins the join.
    :return: chunk_key(chunk's own text) -> caption, as read from that file.
    :raises FileNotFoundError: If assistant_captions_file is set but does not resolve
        to an existing file.
    :raises ValueError: If assistant_captions_file is not set, or the file's content
        is not a JSON object mapping strings to strings.
    """
    if not settings.assistant_captions_file:
        raise ValueError(
            "no captions file configured: set ASSISTANT_CAPTIONS_FILE to build a "
            "'captions' collection"
        )
    path = repo_root / settings.assistant_captions_file
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(value, str) for value in data.values()):
        raise ValueError(f"{path}: captions file must be a JSON object of strings to strings")
    return data


def load_corpus(settings: Settings, repo_root: Path, wave: int) -> list[Document]:
    """Load every Document the corpus manifest names, at the given wave.

    The manifest and per-source loaders are exactly what build_collection() itself
    used to run inline; scripts/assistant/captions.py's `missing` command calls this
    directly so it chunks the identical corpus a real ingest run would, without
    needing a chat model, an embedding server, or a database.

    :param settings: Application settings (private corpus locations).
    :param repo_root: Repository root, passed through to build_manifest.
    :param wave: Highest corpus wave to include (see corpus.py::build_manifest).
    :return: Every Document the manifest's sources load to, public layer first.
    :raises FileNotFoundError: If assistant_private_corpus_manifest is set but does
        not resolve to an existing file (corpus.py::build_manifest).
    :raises ValueError: If a local manifest entry resolves outside every root in
        assistant_private_corpus_dirs, or names an unsupported file suffix
        (corpus.py::build_manifest).
    """
    private_dirs = [Path(entry) for entry in settings.assistant_private_corpus_dirs]
    local_manifest = (
        Path(settings.assistant_private_corpus_manifest)
        if settings.assistant_private_corpus_manifest
        else None
    )
    sources = build_manifest(
        repo_root=repo_root,
        private_dirs=private_dirs,
        wave=wave,
        local_manifest=local_manifest,
    )
    return [doc for source in sources for doc in load_source(source)]


async def build_collection(spec: CollectionSpec, settings: Settings, repo_root: Path) -> int:
    """Build one named collection: load the corpus, chunk it, embed it, store it.

    Rerunning it with an existing spec.name replaces that collection instead of
    appending to it: the build writes every chunk into a staging table and only then
    swaps it live (_publish_collection), so a build that fails before the swap leaves
    the previous collection and its registry row exactly as they were, and the next
    build for that name drops the leftover staging table when it creates a fresh one.

    :param spec: Which chunker/context/wave this collection represents.
    :param settings: Application settings (vector DB URL, embedding model, private
        corpus locations).
    :param repo_root: Repository root, passed through to build_manifest.
    :return: Number of chunks written to the collection.
    :raises FileNotFoundError: If spec.context is "captions" and the configured
        captions file does not exist.
    :raises ValueError: If spec.name is too long to stage a rebuild (see
        staging_table) - checked before any other work, or if spec.context is
        "captions" and load_captions() rejects the configured file - checked before
        the corpus is loaded or embedded, so a misconfigured captions build fails
        immediately rather than after that work - or if every chunk misses a caption
        once the corpus has been chunked.
    """
    captions = load_captions(settings, repo_root) if spec.context == "captions" else None
    staging = staging_table(spec.name)
    local_manifest = (
        Path(settings.assistant_private_corpus_manifest)
        if settings.assistant_private_corpus_manifest
        else None
    )
    # Read before loading, so the registry names exactly the versions this build read.
    # An absolute manifest path wins the join, the same way corpus.py resolves it.
    app_version = git_version(repo_root)
    corpus_version = git_version((repo_root / local_manifest).parent) if local_manifest else None
    documents = load_corpus(settings, repo_root, spec.wave)
    embeddings = make_embeddings(settings)
    chunks = split(documents, spec.chunker, embeddings=embeddings)
    llm = make_chat_model(settings) if spec.context in ("llm_context", "doc_summary") else None
    if captions is not None:
        total = len(chunks)
        missing = sum(1 for chunk in chunks if chunk_key(chunk.page_content) not in captions)
        if chunks and missing == total:
            raise ValueError(
                f"{missing} of {total} chunks have no matching caption; the captions "
                "file probably belongs to another corpus revision or chunker"
            )
        if missing:
            logger.warning(
                "some chunks have no matching caption",
                extra={
                    "event": "assistant_captions_missing",
                    "missing": missing,
                    "total": total,
                },
            )
    chunks = enrich(chunks, spec.context, llm=llm, captions=captions)

    vector_size = len(embeddings.embed_query("dimension probe"))
    engine = make_engine(settings.assistant_vector_db_url)
    try:
        await create_collection(engine, table=staging, vector_size=vector_size, hybrid=False)
        store = open_store(engine, table=staging, embeddings=embeddings)
        if chunks:
            await store.aadd_documents(chunks)
    finally:
        await engine.close()
    await _publish_collection(
        settings.assistant_vector_db_url,
        spec,
        embedding_model=settings.assistant_embedding_model,
        corpus_hash=_corpus_hash(chunks),
        chunk_count=len(chunks),
        app_version=app_version,
        corpus_version=corpus_version,
    )
    return len(chunks)
