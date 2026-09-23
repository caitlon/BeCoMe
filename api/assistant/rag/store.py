"""pgvector-backed storage: connection pool, collection creation, store access.

Talks to the assistant's own vector database (docker-compose profile "assistant",
Settings.assistant_vector_db_url), never the application's own Postgres.
"""

import contextlib

from langchain_core.embeddings import Embeddings
from langchain_postgres import PGEngine, PGVectorStore
from langchain_postgres.v2.hybrid_search_config import HybridSearchConfig
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
    (BCM-129 refreshes an existing collection with a second corpus wave). The no-op
    does not check whether hybrid matches the table's existing shape: a second call
    that flips hybrid for an existing table name silently keeps the old columns.
    BCM-125, which is what first sets hybrid=True, must recreate the table itself
    when switching an existing collection to hybrid.

    :param engine: The assistant database's connection pool.
    :param table: Table name for this collection (pipeline.py names it per variant).
    :param vector_size: Embedding dimensionality, decided by the embedding model.
    :param hybrid: Whether to also provision a full-text-search column for hybrid
        search. This pull request's own pipeline always passes False (dense-only);
        BCM-125's lab is what exercises True.
    :return: None.
    """
    hybrid_config = HybridSearchConfig() if hybrid else None
    with contextlib.suppress(ProgrammingError):
        await engine.ainit_vectorstore_table(
            table_name=table, vector_size=vector_size, hybrid_search_config=hybrid_config
        )


def open_store(engine: PGEngine, table: str, embeddings: Embeddings) -> PGVectorStore:
    """Open an existing collection table as a PGVectorStore.

    :param engine: The assistant database's connection pool.
    :param table: The collection's table name, already created via ensure_collection.
    :param embeddings: The embeddings client used to embed queries and documents.
    :return: A PGVectorStore bound to that table.
    """
    return PGVectorStore.create_sync(engine=engine, embedding_service=embeddings, table_name=table)
