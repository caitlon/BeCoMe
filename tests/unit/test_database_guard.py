"""Tests for the unit-tier guard that keeps a unit test off the database."""

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

RULE = "unit tests use mocks; a test that needs a database belongs in tests/integration"


@pytest.fixture
def engine():
    """In-memory SQLite engine, built but never connected by the fixture."""
    eng = create_engine("sqlite://")
    yield eng
    eng.dispose()


class TestDatabaseGuard:
    """A unit test may build an engine, and may not connect one."""

    def test_building_an_engine_does_not_fail(self, engine):
        """
        GIVEN a unit test
        WHEN it builds an in-memory SQLite engine
        THEN nothing is refused, because create_engine does not connect
        """
        assert engine.dialect.name == "sqlite"

    @pytest.mark.parametrize(
        "connect",
        [
            pytest.param(lambda eng: eng.connect(), id="connect"),
            pytest.param(lambda eng: eng.raw_connection(), id="raw_connection"),
            pytest.param(lambda eng: eng.begin().__enter__(), id="begin"),
            pytest.param(lambda eng: SQLModel.metadata.create_all(eng), id="create_all"),
            pytest.param(lambda eng: Session(eng).execute(text("SELECT 1")), id="session"),
        ],
    )
    def test_connecting_an_engine_fails_with_the_rule(self, engine, connect):
        """
        GIVEN an in-memory SQLite engine
        WHEN a unit test connects it, directly or through begin, create_all or a session
        THEN the test fails with the message naming the unit-test rule
        """
        with pytest.raises(pytest.fail.Exception, match=RULE):
            connect(engine)
