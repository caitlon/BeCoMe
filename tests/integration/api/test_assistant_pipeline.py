"""Integration tests for pipeline.py, and for eval_retrieval.py's read of the registry
it writes, against real PostgreSQL+pgvector and a fake embedding HTTP server (fakes the
model server, not the database)."""

import importlib.util
import json
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import psycopg
import pytest

from api.assistant.rag.chunkers import ChunkerConfig
from api.assistant.rag.pipeline import CollectionSpec, build_collection
from api.assistant.rag.store import make_engine, open_store
from api.config import Settings

pytestmark = pytest.mark.skipif(
    not shutil.which("pg_ctl"), reason="PostgreSQL not installed (pg_ctl not found in PATH)"
)

try:
    from pytest_postgresql import factories

    postgresql_proc = factories.postgresql_proc()
    postgresql = factories.postgresql("postgresql_proc")
except ImportError:
    postgresql_proc = None
    postgresql = None


@pytest.fixture(autouse=True)
def _isolated_from_dotenv(tmp_path, monkeypatch):
    """Run each test where no .env exists, so Settings never sees a developer's real corpus."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ASSISTANT_PRIVATE_CORPUS_MANIFEST", raising=False)
    monkeypatch.delenv("ASSISTANT_PRIVATE_CORPUS_DIRS", raising=False)


class _FakeEmbeddingHandler(BaseHTTPRequestHandler):
    """Answers any POST like a hosted /embeddings endpoint: one fixed 8-d vector per input."""

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        inputs = body.get("input", [""])
        if isinstance(inputs, str):
            inputs = [inputs]
        payload = {
            "data": [{"embedding": [0.1] * 8, "index": i} for i in range(len(inputs))],
            "model": body.get("model", "fake"),
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        }
        response = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format_str, *args):
        pass  # keep pytest output free of one line per fake HTTP request


@pytest.fixture
def fake_embedding_server():
    """Start a local HTTP server answering like a hosted embeddings endpoint."""
    server = HTTPServer(("127.0.0.1", 0), _FakeEmbeddingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        thread.join()


def _connection_url(postgresql) -> str:
    """Build a postgresql+psycopg:// URL from pytest-postgresql's connection info."""
    info = postgresql.info
    return f"postgresql+psycopg://{info.user}:@{info.host}:{info.port}/{info.dbname}"


@pytest.fixture(autouse=True)
def _require_pgvector(postgresql):
    """Skip with a clear reason when this PostgreSQL has no pgvector extension.

    Checked through pg_available_extensions before anything calls CREATE EXTENSION, so
    a developer machine with PostgreSQL but no pgvector next to it (Homebrew's
    postgresql@16 formula does not carry it - see api/assistant/README.md) gets a clear
    skip instead of build_collection's own CREATE EXTENSION IF NOT EXISTS failing with
    sqlalchemy.exc.NotSupportedError. CI is not exposed to this path: Task 124.3's
    "Verify the pgvector extension is installed" step already fails the job before
    pytest runs if the apt install is broken, so a CI run either has pgvector for real
    or never reaches this fixture at all.
    """
    with postgresql.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
        if cursor.fetchone() is None:
            pytest.skip(
                "pgvector is not installed next to this PostgreSQL (see api/assistant/README.md)"
            )


class TestBuildCollection:
    """build_collection loads, chunks, embeds, and stores the whole corpus."""

    @pytest.mark.asyncio
    async def test_builds_a_searchable_collection_from_a_tiny_corpus(
        self, tmp_path, postgresql, fake_embedding_server
    ):
        """
        GIVEN a one-file corpus, a fresh PostgreSQL database, and a fake embedding server
        WHEN build_collection runs with context="none"
        THEN it reports the chunk count, and the collection is searchable afterward
        """
        # GIVEN
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "index.md").write_text(
            "# BeCoMe\n\nBeCoMe combines the arithmetic mean and the median.\n",
            encoding="utf-8",
        )
        settings = Settings(
            secret_key="test-secret-key",
            assistant_vector_db_url=_connection_url(postgresql),
            assistant_embedding_base_url=fake_embedding_server,
            assistant_embedding_model="fake-embedding-model",
        )
        spec = CollectionSpec(
            name="docs_test_pipeline",
            chunker=ChunkerConfig(strategy="markdown_headers", size=500, overlap_pct=10),
            context="none",
            wave=1,
        )

        # WHEN
        chunk_count = await build_collection(spec, settings, repo_root=tmp_path)

        # THEN: query the collection back through a fresh embeddings client pointed
        # at the same fake server - it always returns the same fixed vector
        # regardless of content, so this checks storage and wiring, not relevance.
        assert chunk_count == 1
        from api.assistant.rag.models import make_embeddings

        engine = make_engine(_connection_url(postgresql))
        try:
            query_embeddings = make_embeddings(settings)
            store = open_store(engine, table="docs_test_pipeline", embeddings=query_embeddings)
            results = await store.asimilarity_search_with_score("mean and median", k=1)
            assert len(results) == 1
            assert "arithmetic mean" in results[0][0].page_content
        finally:
            await engine.close()

    @pytest.mark.asyncio
    async def test_builds_a_collection_with_the_semantic_chunking_strategy(
        self, tmp_path, postgresql, fake_embedding_server
    ):
        """
        GIVEN a one-file corpus, a fresh PostgreSQL database, and a fake embedding server
        WHEN build_collection runs with strategy="semantic"
        THEN it succeeds and stores the resulting chunks - proving split() receives the
             same embeddings client the store uses, rather than raising ValueError for
             a missing one
        """
        # GIVEN
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "index.md").write_text(
            "# BeCoMe\n\nBeCoMe combines the arithmetic mean and the median.\n",
            encoding="utf-8",
        )
        settings = Settings(
            secret_key="test-secret-key",
            assistant_vector_db_url=_connection_url(postgresql),
            assistant_embedding_base_url=fake_embedding_server,
            assistant_embedding_model="fake-embedding-model",
        )
        spec = CollectionSpec(
            name="docs_test_pipeline_semantic",
            chunker=ChunkerConfig(strategy="semantic"),
            context="none",
            wave=1,
        )

        # WHEN
        chunk_count = await build_collection(spec, settings, repo_root=tmp_path)

        # THEN
        assert chunk_count == 1
        from api.assistant.rag.models import make_embeddings

        engine = make_engine(_connection_url(postgresql))
        try:
            query_embeddings = make_embeddings(settings)
            store = open_store(
                engine, table="docs_test_pipeline_semantic", embeddings=query_embeddings
            )
            results = await store.asimilarity_search_with_score("mean and median", k=1)
            assert len(results) == 1
            assert "arithmetic mean" in results[0][0].page_content
        finally:
            await engine.close()


def _plain_dsn(url: str) -> str:
    """Strip the "+psycopg" SQLAlchemy driver suffix for a plain psycopg connection."""
    return url.replace("postgresql+psycopg://", "postgresql://")


async def _registry_rows(postgresql, name: str) -> list[tuple]:
    """Read one collection's registry rows back through a plain psycopg connection."""
    dsn = _plain_dsn(_connection_url(postgresql))
    async with await psycopg.AsyncConnection.connect(dsn) as conn, conn.cursor() as cursor:
        await cursor.execute(
            "SELECT chunker_strategy, wave, embedding_model, chunk_count, app_version, "
            "corpus_version FROM assistant_collections WHERE name = %s",
            (name,),
        )
        return await cursor.fetchall()


@pytest.fixture
def tagged_corpus(tmp_path):
    """A local corpus that is its own git repository, tagged wave-1.

    Also lays down a one-file docs/ tree next to it, matching a real checkout's shape,
    for the two tests (TestCollectionRegistry and TestFetchCollectionRow) that need a
    local layer with a real, deterministic corpus_version.

    :return: The corpus directory (tmp_path/supplementary/assistant/corpus).
    """
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("# BeCoMe\n\nOne sentence.\n", encoding="utf-8")
    corpus = tmp_path / "supplementary" / "assistant" / "corpus"
    (corpus / "wave-1").mkdir(parents=True)
    (corpus / "wave-1" / "note.txt").write_text("BeCoMe in one line.", encoding="utf-8")
    (corpus / "manifest.json").write_text(
        json.dumps([{"path": "wave-1/note.txt", "title": "Note", "lang": "en", "wave": 1}]),
        encoding="utf-8",
    )
    for args in (("init",), ("add", "-A"), ("commit", "-m", "wave 1"), ("tag", "wave-1")):
        subprocess.run(  # noqa: S603 - fixed git argv plus a pytest tmp_path
            [  # noqa: S607 - fixed argv, no shell
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "-C",
                str(corpus),
                *args,
            ],
            check=True,
            capture_output=True,
        )
    return corpus


def _tagged_corpus_settings(postgresql, fake_embedding_server, corpus) -> Settings:
    """Settings for a build against tagged_corpus's local corpus.

    :param postgresql: The pytest-postgresql fixture.
    :param fake_embedding_server: fake_embedding_server's base URL.
    :param corpus: tagged_corpus's return value.
    :return: Settings pointed at that database, that fake embedding server, and that
        corpus's manifest.
    """
    return Settings(
        secret_key="test-secret-key",
        assistant_vector_db_url=_connection_url(postgresql),
        assistant_embedding_base_url=fake_embedding_server,
        assistant_embedding_model="fake-embedding-model",
        assistant_private_corpus_dirs=[str(corpus)],
        assistant_private_corpus_manifest=str(corpus / "manifest.json"),
    )


class TestCollectionRegistry:
    """build_collection records every build in the assistant_collections table."""

    @pytest.mark.asyncio
    async def test_records_and_updates_one_row_per_collection_name(
        self, tmp_path, postgresql, fake_embedding_server
    ):
        """
        GIVEN a tiny corpus outside any git repository and a fresh database
        WHEN build_collection runs twice for the same collection name
        THEN assistant_collections holds exactly one row, updated the second time, with
            both versions empty
        """
        # GIVEN
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "index.md").write_text("# BeCoMe\n\nOne sentence.\n", encoding="utf-8")
        settings = Settings(
            secret_key="test-secret-key",
            assistant_vector_db_url=_connection_url(postgresql),
            assistant_embedding_base_url=fake_embedding_server,
            assistant_embedding_model="fake-embedding-model",
        )
        spec = CollectionSpec(
            name="docs_test_registry",
            chunker=ChunkerConfig(strategy="markdown_headers", size=500, overlap_pct=10),
            context="none",
            wave=1,
        )

        # WHEN
        await build_collection(spec, settings, repo_root=tmp_path)
        await build_collection(spec, settings, repo_root=tmp_path)

        # THEN
        rows = await _registry_rows(postgresql, spec.name)
        assert len(rows) == 1
        strategy, wave, embedding_model, chunk_count, app_version, corpus_version = rows[0]
        assert strategy == "markdown_headers"
        assert wave == 1
        assert embedding_model == "fake-embedding-model"
        assert chunk_count == 1
        assert app_version is None
        assert corpus_version is None

    @pytest.mark.asyncio
    async def test_records_the_version_of_a_git_backed_local_corpus(
        self, tmp_path, postgresql, fake_embedding_server, tagged_corpus
    ):
        """
        GIVEN a local corpus that is its own git repository, tagged wave-1
        WHEN build_collection runs with that corpus's manifest
        THEN the registry row carries corpus_version "wave-1"
        """
        # GIVEN
        settings = _tagged_corpus_settings(postgresql, fake_embedding_server, tagged_corpus)
        spec = CollectionSpec(
            name="docs_test_registry_versions",
            chunker=ChunkerConfig(strategy="markdown_headers", size=500, overlap_pct=10),
            context="none",
            wave=1,
        )

        # WHEN
        await build_collection(spec, settings, repo_root=tmp_path)

        # THEN
        rows = await _registry_rows(postgresql, spec.name)
        assert rows[0][-1] == "wave-1"


def _load_eval_retrieval():
    """Import scripts/assistant/eval_retrieval.py by path, since scripts/ is not a package.

    :return: The imported eval_retrieval module.
    """
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "eval_retrieval", root / "scripts" / "assistant" / "eval_retrieval.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_retrieval"] = module
    spec.loader.exec_module(module)
    return module


_eval_retrieval = _load_eval_retrieval()


class TestFetchCollectionRow:
    """eval_retrieval.py's _fetch_collection_row reads back what pipeline.py records.

    An integration test, not a unit test: it runs both sides of the same table against a
    real database, so a future rename of assistant_collections.app_version or
    .corpus_version in pipeline.py's CREATE TABLE/INSERT fails here (UndefinedColumn)
    instead of only surfacing when someone runs the eval script against a real collection.
    """

    @pytest.mark.asyncio
    async def test_reads_back_the_versions_build_collection_recorded(
        self, tmp_path, postgresql, fake_embedding_server, tagged_corpus
    ):
        """
        GIVEN a local corpus that is its own git repository, tagged wave-1, indexed by
            build_collection
        WHEN _fetch_collection_row reads that collection's registry row
        THEN it returns the same app_version and corpus_version the registry holds
        """
        # GIVEN
        settings = _tagged_corpus_settings(postgresql, fake_embedding_server, tagged_corpus)
        vector_db_url = settings.assistant_vector_db_url
        spec = CollectionSpec(
            name="docs_test_fetch_collection_row",
            chunker=ChunkerConfig(strategy="markdown_headers", size=500, overlap_pct=10),
            context="none",
            wave=1,
        )
        await build_collection(spec, settings, repo_root=tmp_path)

        # WHEN
        row = await _eval_retrieval._fetch_collection_row(vector_db_url, spec.name)

        # THEN: matches what the registry actually holds, cross-checked independently
        assert row == (None, "wave-1")
        registry_rows = await _registry_rows(postgresql, spec.name)
        assert row == registry_rows[0][-2:]

    @pytest.mark.asyncio
    async def test_returns_none_for_an_unknown_collection_name(self, postgresql):
        """
        GIVEN a fresh database with no assistant_collections row for a given name
        WHEN _fetch_collection_row looks it up
        THEN it returns None rather than raising
        """
        # WHEN
        row = await _eval_retrieval._fetch_collection_row(
            _connection_url(postgresql), "does_not_exist"
        )

        # THEN
        assert row is None
