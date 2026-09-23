"""pgvector-backed storage: connection pool, collection creation, store access.

Talks to the assistant's own vector database (docker-compose profile "assistant",
Settings.assistant_vector_db_url), never the application's own Postgres.
"""

from langchain_core.embeddings import Embeddings
from langchain_postgres import PGEngine, PGVectorStore
from langchain_postgres.v2.hybrid_search_config import HybridSearchConfig
from psycopg.errors import DuplicateTable
from sqlalchemy.exc import ProgrammingError


def make_engine(url: str) -> PGEngine:
    """Build the connection pool to the assistant's own vector database.

    :param url: SQLAlchemy connection URL (Settings.assistant_vector_db_url).
    :return: A PGEngine wrapping an async connection pool.
    :raises ValueError: If url is empty; the setting has no default, so an unset
        ASSISTANT_VECTOR_DB_URL arrives here as the empty string.
    """
    if not url:
        raise ValueError(
            "ASSISTANT_VECTOR_DB_URL is not set; the assistant's vector database has no "
            "default URL (see env/.env.example)"
        )
    return PGEngine.from_connection_string(url=url)


async def ensure_collection(engine: PGEngine, table: str, vector_size: int, hybrid: bool) -> None:
    """Create the collection's table if it does not already exist.

    Idempotent: calling this again for a table that already exists is a no-op, since
    re-running the ingest CLI for an existing collection name is a normal workflow
    (a second corpus wave refreshes an existing collection). The no-op
    does not check whether hybrid matches the table's existing shape: a second call
    that flips hybrid for an existing table name silently keeps the old columns.
    Whatever first sets hybrid=True must recreate the table itself when switching an
    existing collection to hybrid.

    :param engine: The assistant database's connection pool.
    :param table: Table name for this collection (pipeline.py names it per variant).
    :param vector_size: Embedding dimensionality, decided by the embedding model.
    :param hybrid: Whether to also provision a full-text-search column for hybrid
        search. The ingest pipeline passes False (dense-only); only the later retrieval
        experiments pass True.
    :return: None.
    :raises ProgrammingError: If table creation fails for any reason other than the
        table already existing. Only psycopg.errors.DuplicateTable (SQLSTATE 42P07)
        is treated as an already-created collection; any other ProgrammingError (a
        rejected table name, an invalid column) propagates instead of being silently
        absorbed.
    """
    hybrid_config = HybridSearchConfig() if hybrid else None
    try:
        await engine.ainit_vectorstore_table(
            table_name=table, vector_size=vector_size, hybrid_search_config=hybrid_config
        )
    except ProgrammingError as exc:
        if not isinstance(exc.orig, DuplicateTable):
            raise


def open_store(engine: PGEngine, table: str, embeddings: Embeddings) -> PGVectorStore:
    """Open an existing collection table as a PGVectorStore.

    :param engine: The assistant database's connection pool.
    :param table: The collection's table name, already created via ensure_collection.
    :param embeddings: The embeddings client used to embed queries and documents.
    :return: A PGVectorStore bound to that table.
    """
    return PGVectorStore.create_sync(engine=engine, embedding_service=embeddings, table_name=table)
