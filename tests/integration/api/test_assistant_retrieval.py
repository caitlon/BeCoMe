"""Integration tests for retrieval.py against real PostgreSQL+pgvector."""

import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

from api.assistant.rag.models import make_embeddings
from api.assistant.rag.retrieval import DocsRetriever, RetrievalConfig
from api.assistant.rag.store import ensure_collection, make_engine, open_store
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


class _FakeEmbeddingHandler(BaseHTTPRequestHandler):
    """Answers any POST like a hosted /embeddings endpoint: one 8-d vector per input text.

    The vector comes from langchain_core's own DeterministicFakeEmbedding, hashed from
    the input text, rather than a single constant: a test asserting on relative
    similarity between documents (TestDocsRetrieverAgainstRealPgvector below) needs
    embeddings that actually vary with content, not one identical vector for every
    input.
    """

    _embeddings = DeterministicFakeEmbedding(size=8)

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        inputs = body.get("input", [""])
        if isinstance(inputs, str):
            inputs = [inputs]
        vectors = self._embeddings.embed_documents(inputs)
        payload = {
            "data": [{"embedding": vector, "index": i} for i, vector in enumerate(vectors)],
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
        pass


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
    skip instead of ensure_collection's own CREATE EXTENSION IF NOT EXISTS failing with
    sqlalchemy.exc.NotSupportedError. CI is not exposed to this path: Task 124.3's
    "Verify the pgvector extension is installed" step already fails the job before
    pytest runs if the apt install is broken, so a CI run either has pgvector for real
    or never reaches this fixture at all. Duplicated from Task 124.12/124.14 rather than
    imported, for the same reason fake_embedding_server/_connection_url are duplicated
    above: a pytest fixture imported by parameter name is not something ruff/pyflakes
    reliably recognizes as used.
    """
    with postgresql.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
        if cursor.fetchone() is None:
            pytest.skip(
                "pgvector is not installed next to this PostgreSQL (see api/assistant/README.md)"
            )


class TestDocsRetrieverAgainstRealPgvector:
    """Closes the loop on typing store as VectorStore (CONTRACT ISSUE 2, Task 124.16):
    PGVectorStore must stay a valid argument, not only InMemoryVectorStore in fakes-only
    unit tests."""

    @pytest.mark.asyncio
    async def test_searches_a_real_pgvector_backed_store(self, postgresql, fake_embedding_server):
        """
        GIVEN a PGVectorStore backed by a real pgvector table, with one document added
        WHEN DocsRetriever searches it
        THEN the document comes back as a RetrievedChunk with its metadata mapped
        """
        # GIVEN: the embeddings client comes from the same factory production code uses
        # (not a directly-constructed client class) so this file names no chat-model or
        # embeddings vendor class of its own.
        settings = Settings(
            secret_key="test-secret-key",
            assistant_embedding_base_url=fake_embedding_server,
            assistant_embedding_model="fake-embedding-model",
        )
        embeddings = make_embeddings(settings)
        engine = make_engine(_connection_url(postgresql))
        try:
            await ensure_collection(
                engine, table="docs_test_retrieval", vector_size=8, hybrid=False
            )
            store = open_store(engine, table="docs_test_retrieval", embeddings=embeddings)
            await store.aadd_documents(
                [
                    Document(
                        page_content="BeCoMe combines the mean and the median.",
                        metadata={
                            "title": "Method",
                            "heading_path": "Overview",
                            "url": "https://docs.becomify.app/method-description/",
                            "layer": "public",
                        },
                    )
                ]
            )
            config = RetrievalConfig(mode="dense", k=1)
            retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)

            # WHEN
            results = await retriever.search("mean and median")

            # THEN
            assert len(results) == 1
            assert results[0].title == "Method"
            assert results[0].section == "Overview"
            assert results[0].url == "https://docs.becomify.app/method-description/"
        finally:
            await engine.close()

    @pytest.mark.asyncio
    async def test_scores_rank_the_exact_match_first_in_descending_order(
        self, postgresql, fake_embedding_server
    ):
        """
        GIVEN a PGVectorStore with one document matching the query exactly and one
              document with no textual relation to it
        WHEN DocsRetriever searches for the exact-match text
        THEN the exact-match document comes back first, its score is the higher of
             the two, and the scores are in descending order - proving score means
             "higher is more relevant" against the real store, not the raw distance
             (lower is more relevant) that PGVectorStore's own similarity search
             returns underneath
        """
        # GIVEN: the embeddings client comes from the same factory production code uses,
        # same as test_searches_a_real_pgvector_backed_store above.
        query_text = "BeCoMe combines the mean and the median."
        settings = Settings(
            secret_key="test-secret-key",
            assistant_embedding_base_url=fake_embedding_server,
            assistant_embedding_model="fake-embedding-model",
        )
        embeddings = make_embeddings(settings)
        engine = make_engine(_connection_url(postgresql))
        try:
            await ensure_collection(
                engine, table="docs_test_retrieval_ranking", vector_size=8, hybrid=False
            )
            store = open_store(engine, table="docs_test_retrieval_ranking", embeddings=embeddings)
            await store.aadd_documents(
                [
                    Document(
                        page_content="Cats are small domesticated carnivorous mammals.",
                        metadata={
                            "title": "Unrelated",
                            "heading_path": "",
                            "url": None,
                            "layer": "public",
                        },
                    ),
                    Document(
                        page_content=query_text,
                        metadata={
                            "title": "Method",
                            "heading_path": "Overview",
                            "url": None,
                            "layer": "public",
                        },
                    ),
                ]
            )
            config = RetrievalConfig(mode="dense", k=2)
            retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)

            # WHEN
            results = await retriever.search(query_text)

            # THEN
            assert len(results) == 2
            assert results[0].title == "Method"
            scores = [chunk.score for chunk in results]
            assert results[0].score == max(scores)
            assert scores == sorted(scores, reverse=True)
        finally:
            await engine.close()
