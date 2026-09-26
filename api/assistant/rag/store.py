"""pgvector-backed storage: collection creation, rebuild swap, store access.

Talks to the assistant's own vector database (docker-compose profile "assistant",
Settings.assistant_vector_db_url), never the application's own Postgres.
"""

import re
from typing import Any

import psycopg
from langchain_core.embeddings import Embeddings
from langchain_postgres import PGEngine, PGVectorStore
from langchain_postgres.v2.hybrid_search_config import HybridSearchConfig
from psycopg import sql

# PostgreSQL's own identifier limit is 63 bytes. langchain-postgres 0.0.18 escapes
# table_name in create_collection's own CREATE TABLE call (PGEngine.ainit_vectorstore_table
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


_STAGING_SUFFIX = "_staging"


def staging_table(table: str) -> str:
    """Name the table a rebuild of a collection is written into before it goes live.

    :param table: The collection's table name.
    :return: table followed by "_staging".
    :raises ValueError: If table is not a plain identifier (see _validate_collection_name),
        or is longer than 55 characters, so that its staging name would pass PostgreSQL's
        63-character identifier limit.
    """
    _validate_collection_name(table)
    staging = f"{table}{_STAGING_SUFFIX}"
    if len(staging) > 63:
        raise ValueError(
            f"collection name {table!r} is too long to rebuild: its staging table "
            f"{staging!r} would pass PostgreSQL's 63-character identifier limit, so keep "
            f"collection names to {63 - len(_STAGING_SUFFIX)} characters"
        )
    return staging


async def create_collection(engine: PGEngine, table: str, vector_size: int, hybrid: bool) -> None:
    """Create the collection's table empty, dropping any table of the same name first.

    :param engine: The assistant database's connection pool.
    :param table: Table name to create.
    :param vector_size: Embedding dimensionality, decided by the embedding model.
    :param hybrid: Whether to also provision a full-text-search column for hybrid
        search. The ingest pipeline passes False (dense-only), and so do the
        retrieval experiments: their hybrid mode fuses dense and BM25 search in
        process, by reciprocal rank fusion, rather than through this column.
    :return: None.
    :raises ValueError: If table is not a plain identifier; see _validate_collection_name.
    """
    _validate_collection_name(table)
    hybrid_config = HybridSearchConfig() if hybrid else None
    await engine.ainit_vectorstore_table(
        table_name=table,
        vector_size=vector_size,
        hybrid_search_config=hybrid_config,
        overwrite_existing=True,
    )


async def swap_in_staging(conn: psycopg.AsyncConnection[Any], table: str) -> None:
    """Replace a collection's live table with its staging table, in the caller's transaction.

    Both statements are DDL, which PostgreSQL runs transactionally: until the caller
    commits, readers keep seeing the old table, and a rollback leaves it in place. The
    staging table's primary-key index keeps its name; PostgreSQL picks a free name for
    the next staging table's own index, so repeated rebuilds never collide on it.

    :param conn: An open connection to the assistant's database; the caller commits.
    :param table: The collection's table name; staging_table(table) must exist.
    :return: None.
    :raises ValueError: If table cannot be staged; see staging_table.
    :raises psycopg.errors.UndefinedTable: If the staging table does not exist.
    """
    staging = staging_table(table)
    # A table name cannot be a query parameter, so sql.Identifier quotes it instead, on
    # top of the plain-identifier check above. Rendered to a string before execute(),
    # where a static scanner rule for SQLAlchemy misreads sql.SQL().format() as injection.
    drop_live = sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table)).as_string(conn)
    rename_staging = (
        sql.SQL("ALTER TABLE {} RENAME TO {}")
        .format(sql.Identifier(staging), sql.Identifier(table))
        .as_string(conn)
    )
    await conn.execute(drop_live)
    await conn.execute(rename_staging)


def open_store(engine: PGEngine, table: str, embeddings: Embeddings) -> PGVectorStore:
    """Open an existing collection table as a PGVectorStore.

    :param engine: The assistant database's connection pool.
    :param table: The collection's table name, already created via create_collection.
    :param embeddings: The embeddings client used to embed queries and documents.
    :return: A PGVectorStore bound to that table.
    :raises ValueError: If table is not a plain identifier; see _validate_collection_name.
    """
    _validate_collection_name(table)
    return PGVectorStore.create_sync(engine=engine, embedding_service=embeddings, table_name=table)
