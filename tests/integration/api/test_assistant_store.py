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

from api.assistant.rag.store import (
    create_collection,
    make_engine,
    open_store,
    staging_table,
    swap_in_staging,
)

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
    skip instead of create_collection's own CREATE EXTENSION IF NOT EXISTS failing with
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


class TestCreateCollection:
    """create_collection creates the pgvector-backed table for one collection."""

    @pytest.mark.asyncio
    async def test_replaces_an_existing_table(self, postgresql):
        """
        GIVEN a table created by create_collection, holding one document
        WHEN create_collection runs again with the same table name
        THEN the table exists empty - the previous table and its row are gone, not
             left alongside a second table or a second row
        """
        # GIVEN
        engine = make_engine(_connection_url(postgresql))
        embeddings = DeterministicFakeEmbedding(size=8)
        try:
            await create_collection(engine, table="docs_test_replace", vector_size=8, hybrid=False)
            store = open_store(engine, table="docs_test_replace", embeddings=embeddings)
            await store.aadd_documents(
                [Document(page_content="BeCoMe combines the mean and the median.")]
            )

            # WHEN
            await create_collection(engine, table="docs_test_replace", vector_size=8, hybrid=False)
        finally:
            await engine.close()

        # THEN
        with postgresql.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM docs_test_replace")
            assert cursor.fetchone()[0] == 0

    @pytest.mark.asyncio
    async def test_creates_a_hybrid_table(self, postgresql):
        """
        GIVEN a fresh PostgreSQL database
        WHEN create_collection runs with hybrid=True
        THEN the tsvector column langchain-postgres provisions for hybrid search
             (content_tsv, per the installed langchain-postgres 0.0.18 source) exists
             on the table alongside the vector column
        """
        # GIVEN
        engine = make_engine(_connection_url(postgresql))

        # WHEN
        try:
            await create_collection(engine, table="docs_test_hybrid", vector_size=8, hybrid=True)
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


class TestOpenStore:
    """open_store binds a PGVectorStore to an already-created collection table."""

    @pytest.mark.asyncio
    async def test_round_trips_a_document_through_real_pgvector(self, postgresql):
        """
        GIVEN a table created by create_collection
        WHEN a document is added through open_store's PGVectorStore and searched for
        THEN the same document comes back
        """
        # GIVEN
        engine = make_engine(_connection_url(postgresql))
        embeddings = DeterministicFakeEmbedding(size=8)
        try:
            await create_collection(
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


async def _seed_live_and_staging(postgresql, table: str) -> None:
    """Create table and its staging table, holding one document each: "old" and "new".

    :param postgresql: The pytest-postgresql fixture.
    :param table: The live table's name; staging_table(table) is created alongside it.
    """
    engine = make_engine(_connection_url(postgresql))
    embeddings = DeterministicFakeEmbedding(size=8)
    try:
        await create_collection(engine, table=table, vector_size=8, hybrid=False)
        live_store = open_store(engine, table=table, embeddings=embeddings)
        await live_store.aadd_documents([Document(page_content="old")])

        staging = staging_table(table)
        await create_collection(engine, table=staging, vector_size=8, hybrid=False)
        staging_store = open_store(engine, table=staging, embeddings=embeddings)
        await staging_store.aadd_documents([Document(page_content="new")])
    finally:
        await engine.close()


class TestSwapInStaging:
    """swap_in_staging replaces a collection's live table with its staging table."""

    @pytest.mark.asyncio
    async def test_commit_puts_the_staging_rows_live(self, postgresql):
        """
        GIVEN a live table holding "old" and a staging table holding "new"
        WHEN swap_in_staging runs and the caller commits
        THEN the live table holds only "new", and the staging table is gone
        """
        # GIVEN
        await _seed_live_and_staging(postgresql, "docs_test_swap_commit")
        dsn = _connection_url(postgresql).replace("postgresql+psycopg://", "postgresql://")

        # WHEN
        async with await psycopg.AsyncConnection.connect(dsn) as conn:
            await swap_in_staging(conn, "docs_test_swap_commit")
            await conn.commit()

        # THEN
        with postgresql.cursor() as cursor:
            cursor.execute("SELECT content FROM docs_test_swap_commit")
            assert cursor.fetchall() == [("new",)]
            cursor.execute("SELECT to_regclass('public.docs_test_swap_commit_staging')")
            assert cursor.fetchone()[0] is None

    @pytest.mark.asyncio
    async def test_rollback_keeps_the_old_table(self, postgresql):
        """
        GIVEN a live table holding "old" and a staging table holding "new"
        WHEN swap_in_staging runs and the caller rolls back instead of committing
        THEN the live table still holds "old", and the staging table still exists
        """
        # GIVEN
        await _seed_live_and_staging(postgresql, "docs_test_swap_rollback")
        dsn = _connection_url(postgresql).replace("postgresql+psycopg://", "postgresql://")

        # WHEN
        async with await psycopg.AsyncConnection.connect(dsn) as conn:
            await swap_in_staging(conn, "docs_test_swap_rollback")
            await conn.rollback()

        # THEN
        with postgresql.cursor() as cursor:
            cursor.execute("SELECT content FROM docs_test_swap_rollback")
            assert cursor.fetchall() == [("old",)]
            cursor.execute("SELECT to_regclass('public.docs_test_swap_rollback_staging')")
            assert cursor.fetchone()[0] is not None

    @pytest.mark.asyncio
    async def test_gives_up_when_a_reader_holds_the_live_table(self, postgresql, monkeypatch):
        """
        GIVEN a live table holding "old" and a staging table holding "new", and a
             second connection that has run SELECT count(*) on the live table inside
             a transaction it keeps open
        WHEN swap_in_staging runs on another connection with _SWAP_LOCK_TIMEOUT
             monkeypatched to "200ms"
        THEN it raises psycopg.errors.LockNotAvailable, and after rolling that
             connection back and closing the reader, the live table still holds only
             "old" and the staging table still exists
        """
        # GIVEN
        await _seed_live_and_staging(postgresql, "docs_test_swap_timeout")
        dsn = _connection_url(postgresql).replace("postgresql+psycopg://", "postgresql://")
        monkeypatch.setattr("api.assistant.rag.store._SWAP_LOCK_TIMEOUT", "200ms")

        reader = await psycopg.AsyncConnection.connect(dsn)
        swap_conn = await psycopg.AsyncConnection.connect(dsn)
        try:
            await reader.execute("SELECT count(*) FROM docs_test_swap_timeout")

            # WHEN / THEN
            with pytest.raises(psycopg.errors.LockNotAvailable):
                await swap_in_staging(swap_conn, "docs_test_swap_timeout")
            await swap_conn.rollback()
        finally:
            await swap_conn.close()
            await reader.close()

        # THEN
        with postgresql.cursor() as cursor:
            cursor.execute("SELECT content FROM docs_test_swap_timeout")
            assert cursor.fetchall() == [("old",)]
            cursor.execute("SELECT to_regclass('public.docs_test_swap_timeout_staging')")
            assert cursor.fetchone()[0] is not None
