"""Unit tests for store.py that need no database."""

import pytest
from psycopg.errors import DuplicateTable, InsufficientPrivilege
from sqlalchemy.exc import ProgrammingError

from api.assistant.rag.store import ensure_collection, make_engine, open_store


def test_make_engine_refuses_an_empty_url():
    """
    GIVEN no ASSISTANT_VECTOR_DB_URL (the setting has no default)
    WHEN make_engine is called with the empty string
    THEN it raises ValueError naming the variable, before any connection attempt
    """
    # WHEN/THEN
    with pytest.raises(ValueError, match="ASSISTANT_VECTOR_DB_URL"):
        make_engine("")


# Each name breaks _COLLECTION_NAME_PATTERN in exactly one way. table="" in the old
# integration suite exercised this same rejection over a real connection (an empty
# identifier is a Postgres syntax error, not psycopg.errors.DuplicateTable); now that
# validation runs before either function touches the library, that case belongs here
# too, alongside the others, and never reaches a database at all.
_MALFORMED_COLLECTION_NAMES = [
    pytest.param('docs"default', id="double-quote"),
    pytest.param("docs;default", id="semicolon"),
    pytest.param("docs default", id="space"),
    pytest.param("Docs_default", id="uppercase-letter"),
    pytest.param("1docs_default", id="leading-digit"),
    pytest.param("a" * 64, id="64-characters"),
    pytest.param("", id="empty"),
]


class TestEnsureCollectionValidatesTheName:
    """ensure_collection refuses a malformed table name before touching the database."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("name", _MALFORMED_COLLECTION_NAMES)
    async def test_refuses_a_malformed_name(self, name):
        """
        GIVEN a table name that is not a plain lowercase identifier
        WHEN ensure_collection is called with it
        THEN it raises ValueError naming the rule and repeating the name, without
             ever using engine - None stands in for PGEngine here, since validation
             must reject the name before anything tries to call ainit_vectorstore_table
        """
        # WHEN/THEN
        with pytest.raises(ValueError, match="is not a plain identifier") as exc_info:
            await ensure_collection(None, table=name, vector_size=8, hybrid=False)
        assert repr(name) in str(exc_info.value)


class TestOpenStoreValidatesTheName:
    """open_store refuses a malformed table name before touching the database."""

    @pytest.mark.parametrize("name", _MALFORMED_COLLECTION_NAMES)
    def test_refuses_a_malformed_name(self, name):
        """
        GIVEN a table name that is not a plain lowercase identifier
        WHEN open_store is called with it
        THEN it raises ValueError naming the rule and repeating the name, without
             ever using engine or embeddings - None stands in for both here, since
             validation must reject the name before PGVectorStore.create_sync runs
        """
        # WHEN/THEN
        with pytest.raises(ValueError, match="is not a plain identifier") as exc_info:
            open_store(None, table=name, embeddings=None)
        assert repr(name) in str(exc_info.value)


class _StubEngineRaisingProgrammingError:
    """Stands in for PGEngine: ainit_vectorstore_table always fails the way a
    permission error would - a real ProgrammingError that is not DuplicateTable -
    so the re-raise branch in ensure_collection is exercised without a real database.
    """

    async def ainit_vectorstore_table(self, **kwargs: object) -> None:
        raise ProgrammingError(
            "CREATE EXTENSION IF NOT EXISTS vector",
            {},
            InsufficientPrivilege('permission denied to create extension "vector"'),
        )


class TestEnsureCollectionReraisesOtherProgrammingErrors:
    """The DuplicateTable-only handling in ensure_collection must not swallow other
    ProgrammingErrors - previously exercised over a real connection with an invalid
    table name (an empty string raised a syntax error); that trigger is gone now that
    validation rejects an invalid name first, so a stub engine takes its place to keep
    the branch covered - a permission error is a realistic stand-in, since the
    assistant's vector database could gain a least-privilege role later the way the
    application database already has (docs/security.md).
    """

    @pytest.mark.asyncio
    async def test_a_non_duplicate_programming_error_still_propagates(self):
        """
        GIVEN a stub engine whose ainit_vectorstore_table raises a ProgrammingError
             that is not psycopg.errors.DuplicateTable
        WHEN ensure_collection is called with a name that passes validation
        THEN the ProgrammingError propagates instead of being swallowed as though the
             collection were already there
        """
        # WHEN/THEN
        with pytest.raises(ProgrammingError) as exc_info:
            await ensure_collection(
                _StubEngineRaisingProgrammingError(),
                table="docs_default",
                vector_size=8,
                hybrid=False,
            )
        assert not isinstance(exc_info.value.orig, DuplicateTable)
