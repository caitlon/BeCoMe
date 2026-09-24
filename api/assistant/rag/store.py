"""pgvector-backed storage: connection pool, collection creation, store access.

Talks to the assistant's own vector database (docker-compose profile "assistant",
Settings.assistant_vector_db_url), never the application's own Postgres.
"""

import re

from langchain_core.embeddings import Embeddings
from langchain_postgres import PGEngine, PGVectorStore
from langchain_postgres.v2.hybrid_search_config import HybridSearchConfig
from psycopg.errors import DuplicateTable
from sqlalchemy.exc import ProgrammingError

# PostgreSQL's own identifier limit is 63 bytes. langchain-postgres 0.0.18 escapes
# table_name in ensure_collection's own CREATE TABLE call (PGEngine.ainit_vectorstore_table
# doubles an embedded double quote), but open_store's later PGVectorStore/AsyncPGVectorStore
# interpolates table_name straight into its insert, search and delete SQL with no escaping
# at all - a name containing a double quote breaks out of the quoted identifier there. Both
# functions are restricted to this plain shape instead, so neither has to rely on the
# library escaping it correctly. fullmatch (not match) so a trailing newline cannot slip a
# name past the $ anchor - re.match(r"...$", "docs_default\n") matches "docs_default" and
# would wrongly accept it; fullmatch requires the whole string to fit the pattern.
_COLLECTION_NAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _validate_collection_name(name: str) -> None:
    """Refuse a collection name that is not a plain, safe SQL identifier.

    :param name: The proposed collection/table name.
    :return: None.
    :raises ValueError: If name does not match _COLLECTION_NAME_PATTERN: lowercase
        letters, digits and underscores, not starting with a digit, at most 63
        characters. Never includes the database URL - only the name and the rule.
    """
    if not _COLLECTION_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            f"collection name {name!r} is not a plain identifier: it must match "
            f"{_COLLECTION_NAME_PATTERN.pattern!r} (lowercase letters, digits and "
            "underscores, not starting with a digit, at most 63 characters)"
        )


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
        search. The ingest pipeline passes False (dense-only), and so do the
        retrieval experiments: their hybrid mode fuses dense and BM25 search in
        process, by reciprocal rank fusion, rather than through this column.
    :return: None.
    :raises ValueError: If table is not a plain identifier; see _validate_collection_name.
    :raises ProgrammingError: If table creation fails for any reason other than the
        table already existing. Only psycopg.errors.DuplicateTable (SQLSTATE 42P07)
        is treated as an already-created collection; any other ProgrammingError (an
        invalid column, a permission error) propagates instead of being silently
        absorbed.
    """
    _validate_collection_name(table)
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
    :raises ValueError: If table is not a plain identifier; see _validate_collection_name.
    """
    _validate_collection_name(table)
    return PGVectorStore.create_sync(engine=engine, embedding_service=embeddings, table_name=table)
