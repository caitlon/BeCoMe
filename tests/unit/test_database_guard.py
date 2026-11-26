"""Tests for the unit-tier guard that keeps a unit test off the database."""

import sqlite3
import sqlite3.dbapi2
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.pool import QueuePool, SingletonThreadPool
from sqlmodel import Session, SQLModel, create_engine

from tests.unit.conftest import _refusals

pytest_plugins = ["pytester"]

# Taken at import, before any test has run under the guard.
_REAL_SQLITE3_CONNECT = sqlite3.connect

RULE = "unit tests use mocks; a test that needs a database belongs in tests/integration"

_INNER_CONFTEST = (
    "from tests.unit.conftest import (  # noqa: F401\n"
    "    _no_swallowed_database_refusal,\n"
    "    pytest_runtest_call,\n"
    "    pytest_runtest_setup,\n"
    "    pytest_runtest_teardown,\n"
    ")\n"
)
_INNER_ARGS = ("-p", "no:cacheprovider", "-o", "asyncio_default_fixture_loop_scope=function")
# A unix socket directory that does not exist: if the guard were missing, libpq would fail
# at once and never reach the network.
_NO_SERVER = "host=/nonexistent-database-socket-dir"


@pytest.fixture(autouse=True)
def _forget_deliberate_refusals() -> Iterator[None]:
    """Remove the refusals these tests cause, so the root check sees only real leaks.

    :yield: Control to the test.
    """
    seen = len(_refusals)
    yield
    del _refusals[seen:]


@pytest.fixture
def engine():
    """In-memory SQLite engine, built but never connected by the fixture."""
    eng = create_engine("sqlite://")
    yield eng
    eng.dispose()


def _run(pytester, source: str | None = None):
    """Run the files of ``pytester`` in this process, with this test's own sqlite3 guard lifted.

    :param pytester: The ``pytester`` fixture.
    :param source: A test module to write next to the guard's conftest; None when the caller
        has written its own files.
    :return: The result of the inner run.
    """
    if source is not None:
        pytester.makeconftest(_INNER_CONFTEST)
        pytester.makepyfile(source)
    with pytest.MonkeyPatch.context() as lift:
        lift.setattr(sqlite3, "connect", _REAL_SQLITE3_CONNECT)
        return pytester.runpytest_inprocess(*_INNER_ARGS)


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
            pytest.param(lambda eng: eng.pool.connect(), id="pool_checkout"),
            pytest.param(lambda _: QueuePool(lambda: object()).connect(), id="pool_creator"),
            pytest.param(
                lambda _: SingletonThreadPool(lambda: object()).connect(), id="singleton_pool"
            ),
            pytest.param(lambda _: sqlite3.connect(":memory:"), id="sqlite3"),
            pytest.param(lambda _: sqlite3.dbapi2.connect(":memory:"), id="sqlite3_dbapi2"),
            pytest.param(
                lambda _: pytest.importorskip("psycopg").connect(_NO_SERVER), id="psycopg"
            ),
            pytest.param(
                lambda _: pytest.importorskip("psycopg2").connect(_NO_SERVER), id="psycopg2"
            ),
        ],
    )
    def test_connecting_fails_with_the_rule(self, engine, connect):
        """
        GIVEN an in-memory SQLite engine
        WHEN a unit test connects it, through the pool or a DBAPI driver, or any way above them
        THEN the test fails with the message naming the unit-test rule
        """
        with pytest.raises(pytest.fail.Exception, match=RULE):
            connect(engine)

    @pytest.mark.parametrize(
        "swallow",
        [
            pytest.param(
                "try:\n        sqlite3.connect(':memory:')\n    except BaseException:\n"
                "        pass",
                id="except",
            ),
            pytest.param(
                "t = threading.Thread(target=lambda: sqlite3.connect(':memory:'))\n"
                "    t.start()\n    t.join()",
                id="thread",
            ),
        ],
    )
    def test_a_swallowed_refusal_fails_the_test(self, pytester, swallow):
        """GIVEN code that swallows the refusal, WHEN the test passes, THEN it errors at teardown."""
        source = f"import sqlite3, threading\n\ndef test_swallows():\n    {swallow}\n"

        result = _run(pytester, source)

        result.assert_outcomes(passed=1, errors=1)
        result.stdout.fnmatch_lines(["*tried to open a database: sqlite3.connect*"])

    @pytest.mark.parametrize(
        ("before", "after", "outcomes"),
        [
            pytest.param("sqlite3.connect(':memory:')", "pass", {"errors": 1}, id="setup"),
            pytest.param(
                "pass", "sqlite3.connect(':memory:')", {"passed": 1, "errors": 1}, id="teardown"
            ),
        ],
    )
    def test_a_module_fixture_that_connects_fails(self, pytester, before, after, outcomes):
        """GIVEN a module-scoped fixture that connects, WHEN its test runs, THEN it errors."""
        source = f"""
            import pytest, sqlite3

            @pytest.fixture(scope="module")
            def database():
                {before}
                yield
                {after}

            def test_uses_it(database):
                pass
            """

        result = _run(pytester, source)

        result.assert_outcomes(**outcomes)
        result.stdout.fnmatch_lines([f"*{RULE}*"])

    def test_a_test_outside_the_unit_tree_may_connect(self, pytester):
        """GIVEN a unit test and another tree, WHEN both run, THEN only the unit one is guarded."""
        for tree in ("a_unit", "b_integration"):
            pytester.mkdir(tree)
        (pytester.path / "a_unit" / "conftest.py").write_text(_INNER_CONFTEST)
        (pytester.path / "a_unit" / "test_a.py").write_text("def test_a():\n    pass\n")
        (pytester.path / "b_integration" / "test_b.py").write_text(
            "import sqlite3\n\ndef test_b():\n    sqlite3.connect(':memory:').close()\n"
        )

        result = _run(pytester)

        result.assert_outcomes(passed=2)
