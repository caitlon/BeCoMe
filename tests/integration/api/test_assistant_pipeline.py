"""Integration tests for pipeline.py against real PostgreSQL+pgvector and a fake
embedding HTTP server (fakes the model server, not the database)."""

import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

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
