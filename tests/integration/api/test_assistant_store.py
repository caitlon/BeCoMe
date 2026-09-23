"""Integration tests for store.py against a real, temporary PostgreSQL + pgvector.

Skipped (like tests/integration/api/db/test_postgres_integration.py) when pg_ctl is not
on PATH - a machine with no PostgreSQL at all. Also skipped, by _require_pgvector below,
when PostgreSQL is present but pgvector is not (a Homebrew postgresql@16 machine that
never built pgvector - see api/assistant/README.md). CI is not exposed to either skip:
ci.yml installs postgresql-16-pgvector and a dedicated step fails the job before
pytest runs if that install is broken, so a broken CI install never reaches this file at
all - PGEngine.ainit_vectorstore_table's own CREATE EXTENSION IF NOT EXISTS vector would
raise there uncaught, but that path is CI-only and already gated earlier.
"""

import shutil
from typing import Any

import psycopg
import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from psycopg.errors import DuplicateTable
from sqlalchemy.exc import ProgrammingError

from api.assistant.rag.store import ensure_collection, make_engine, open_store

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


def _connection_url(postgresql: psycopg.Connection[tuple[Any, ...]]) -> str:
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
    sqlalchemy.exc.NotSupportedError. CI is not exposed to this path: its
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


class TestEnsureCollection:
    """ensure_collection creates the pgvector-backed table for one collection."""

    @pytest.mark.asyncio
    async def test_creates_a_dense_only_table_and_is_idempotent(self, postgresql):
        """
        GIVEN a fresh PostgreSQL database
        WHEN ensure_collection runs twice with hybrid=False and the same table name
        THEN neither call raises - the second finds the table already there
        """
        # GIVEN
        engine = make_engine(_connection_url(postgresql))

        # WHEN/THEN
        try:
            await ensure_collection(engine, table="docs_test_dense", vector_size=8, hybrid=False)
            await ensure_collection(engine, table="docs_test_dense", vector_size=8, hybrid=False)
        finally:
            await engine.close()

    @pytest.mark.asyncio
    async def test_creates_a_hybrid_table(self, postgresql):
        """
        GIVEN a fresh PostgreSQL database
        WHEN ensure_collection runs with hybrid=True
        THEN the tsvector column langchain-postgres provisions for hybrid search
             (content_tsv, per the installed langchain-postgres 0.0.18 source) exists
             on the table alongside the vector column
        """
        # GIVEN
        engine = make_engine(_connection_url(postgresql))

        # WHEN
        try:
            await ensure_collection(engine, table="docs_test_hybrid", vector_size=8, hybrid=True)
        finally:
            await engine.close()

        # THEN
        with postgresql.cursor() as cursor:
            cursor.execute(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'docs_test_hybrid' AND column_name = 'content_tsv'"
            )
            row = cursor.fetchone()
        assert row is not None, "content_tsv column was not provisioned for hybrid search"
        assert row[0] == "tsvector"

    @pytest.mark.asyncio
    async def test_a_non_duplicate_table_error_still_propagates(self, postgresql):
        """
        GIVEN a table name Postgres rejects for a reason other than "already exists"
             (the empty string: the generated CREATE TABLE "public".""(...) is a
             syntax error, not psycopg.errors.DuplicateTable)
        WHEN ensure_collection is called with that name
        THEN the ProgrammingError propagates instead of being swallowed as though the
             collection were already there
        """
        # GIVEN
        engine = make_engine(_connection_url(postgresql))

        # WHEN/THEN
        try:
            with pytest.raises(ProgrammingError) as exc_info:
                await ensure_collection(engine, table="", vector_size=8, hybrid=False)
            assert not isinstance(exc_info.value.orig, DuplicateTable)
        finally:
            await engine.close()


class TestOpenStore:
    """open_store binds a PGVectorStore to an already-created collection table."""

    @pytest.mark.asyncio
    async def test_round_trips_a_document_through_real_pgvector(self, postgresql):
        """
        GIVEN a table created by ensure_collection
        WHEN a document is added through open_store's PGVectorStore and searched for
        THEN the same document comes back
        """
        # GIVEN
        engine = make_engine(_connection_url(postgresql))
        embeddings = DeterministicFakeEmbedding(size=8)
        try:
            await ensure_collection(
                engine, table="docs_test_roundtrip", vector_size=8, hybrid=False
            )
            store = open_store(engine, table="docs_test_roundtrip", embeddings=embeddings)

            # WHEN
            await store.aadd_documents(
                [
                    Document(
                        page_content="BeCoMe combines the mean and the median.",
                        metadata={"title": "Method"},
                    )
                ]
            )
            results = await store.asimilarity_search_with_score("mean and median", k=1)

            # THEN
            assert len(results) == 1
            assert results[0][0].page_content == "BeCoMe combines the mean and the median."
        finally:
            await engine.close()
