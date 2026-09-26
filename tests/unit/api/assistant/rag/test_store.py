"""Unit tests for store.py that need no database."""

import pytest

from api.assistant.rag.store import create_collection, make_engine, open_store, staging_table


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


class TestCreateCollectionValidatesTheName:
    """create_collection refuses a malformed table name before touching the database."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("name", _MALFORMED_COLLECTION_NAMES)
    async def test_refuses_a_malformed_name(self, name):
        """
        GIVEN a table name that is not a plain lowercase identifier
        WHEN create_collection is called with it
        THEN it raises ValueError naming the rule and repeating the name, without
             ever using engine - None stands in for PGEngine here, since validation
             must reject the name before anything tries to call ainit_vectorstore_table
        """
        # WHEN/THEN
        with pytest.raises(ValueError, match="is not a plain identifier") as exc_info:
            await create_collection(None, table=name, vector_size=8, hybrid=False)
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


class TestStagingTable:
    """staging_table names the table a rebuild writes into before it goes live."""

    def test_appends_staging_to_the_name(self):
        """
        GIVEN a plain collection name
        WHEN staging_table is called with it
        THEN it returns the name followed by "_staging"
        """
        # WHEN
        result = staging_table("docs_default")

        # THEN
        assert result == "docs_default_staging"

    def test_accepts_a_55_character_name(self):
        """
        GIVEN a 55-character collection name - the longest whose staging name still
             fits PostgreSQL's 63-character identifier limit
        WHEN staging_table is called with it
        THEN it returns the 63-character staging name, raising nothing
        """
        # GIVEN
        name = "a" * 55

        # WHEN
        result = staging_table(name)

        # THEN
        assert result == name + "_staging"
        assert len(result) == 63

    def test_refuses_a_56_character_name(self):
        """
        GIVEN a 56-character collection name - one character too long, since its
             staging name would be 64 characters
        WHEN staging_table is called with it
        THEN it raises ValueError naming why: too long to rebuild
        """
        # GIVEN
        name = "a" * 56

        # WHEN/THEN
        with pytest.raises(ValueError, match="too long to rebuild"):
            staging_table(name)

    @pytest.mark.parametrize("name", _MALFORMED_COLLECTION_NAMES)
    def test_refuses_a_malformed_name(self, name):
        """
        GIVEN a table name that is not a plain lowercase identifier
        WHEN staging_table is called with it
        THEN it raises ValueError naming the rule and repeating the name, the same
             way _validate_collection_name does for create_collection and open_store
        """
        # WHEN/THEN
        with pytest.raises(ValueError, match="is not a plain identifier") as exc_info:
            staging_table(name)
        assert repr(name) in str(exc_info.value)
