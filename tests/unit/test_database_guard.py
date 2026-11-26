"""Tests for the unit-tier guard that keeps a unit test off the database."""

import asyncio
import sqlite3
import sqlite3.dbapi2
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.pool import QueuePool, SingletonThreadPool
from sqlmodel import Session, SQLModel, create_engine

from tests.unit import conftest as guard

pytest_plugins = ["pytester"]

RULE = "unit tests use mocks; a test that needs a database belongs in tests/integration"

_INNER_CONFTEST = (
    "from tests.unit.conftest import (  # noqa: F401\n"
    "    pytest_runtest_makereport,\n"
    "    pytest_runtest_protocol,\n"
    "    pytest_runtest_teardown,\n"
    "    pytest_sessionfinish,\n"
    ")\n"
)
_INNER_ARGS = ("-p", "no:cacheprovider", "-o", "asyncio_default_fixture_loop_scope=function")
# A unix socket directory that does not exist: if the guard were missing, libpq would fail
# at once and never reach the network.
_NO_SERVER = "host=/nonexistent-database-socket-dir"
_SWALLOW = "try:\n        sqlite3.connect(':memory:')\n    except BaseException:\n        pass"


@pytest.fixture(autouse=True)
def _forget_deliberate_refusals() -> Iterator[None]:
    """Remove the refusals these tests cause, so the teardown check sees only real leaks.

    :yield: Control to the test.
    """
    seen = len(guard._refusals)
    yield
    del guard._refusals[seen:]


@pytest.fixture
def engine():
    """In-memory SQLite engine, built but never connected by the fixture."""
    eng = create_engine("sqlite://")
    yield eng
    eng.dispose()


def _run(pytester, source: str | None = None, *, root: Path | None = None, hooks: str = ""):
    """Run the files of ``pytester`` in this process, guarding the items under ``root``.

    :param pytester: The ``pytester`` fixture.
    :param source: A test module to write next to the guard's conftest; None when the caller
        has written its own files.
    :param root: The directory that stands in for ``tests/unit``; the test directory itself
        by default.
    :param hooks: Source added to the guard's conftest.
    :return: The result of the inner run.
    """
    if source is not None:
        pytester.makeconftest(_INNER_CONFTEST + hooks)
        pytester.makepyfile(source)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(guard, "_UNIT_ROOT", root or pytester.path)
        return pytester.runpytest_inprocess(*_INNER_ARGS)


class TestDatabaseGuard:
    """A unit test may build an engine, and may not connect one."""

    def test_building_an_engine_does_not_fail(self, engine):
        """GIVEN a unit test, WHEN it builds an engine, THEN nothing is refused: it never connects."""
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
                lambda _: pytest.importorskip("psycopg").Connection.connect(_NO_SERVER),
                id="psycopg_connection",
            ),
            pytest.param(
                lambda _: pytest.importorskip("psycopg").AsyncConnection.connect(_NO_SERVER),
                id="psycopg_async_connection",
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

    def test_the_wrapped_drivers_still_connect_outside_a_unit_item(self, monkeypatch):
        """GIVEN the guard is off, WHEN psycopg connects, THEN the driver fails with its own error."""
        psycopg = pytest.importorskip("psycopg")
        monkeypatch.setattr(guard, "_active", False)

        for connect in (psycopg.connect, psycopg.Connection.connect):
            with pytest.raises(psycopg.OperationalError):
                connect(_NO_SERVER)
        with pytest.raises(psycopg.OperationalError):
            asyncio.run(psycopg.AsyncConnection.connect(_NO_SERVER))

    @pytest.mark.parametrize(
        "swallow",
        [
            pytest.param(_SWALLOW, id="except"),
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

    def test_a_refused_test_is_reported_once(self, pytester):
        """GIVEN a test that connects, WHEN it runs, THEN it fails once, with no teardown error."""
        source = "import sqlite3\n\ndef test_connects():\n    sqlite3.connect(':memory:')\n"

        result = _run(pytester, source)

        result.assert_outcomes(failed=1)
        result.stdout.fnmatch_lines([f"*{RULE}*"])

    @pytest.mark.parametrize(
        ("before", "after", "outcomes", "message"),
        [
            pytest.param("sqlite3.connect(':memory:')", "pass", {"errors": 1}, RULE, id="setup"),
            pytest.param(
                "pass",
                "sqlite3.connect(':memory:')",
                {"passed": 1, "errors": 1},
                RULE,
                id="teardown",
            ),
            pytest.param(
                "pass",
                "try: sqlite3.connect(':memory:')\n                except BaseException: pass",
                {"passed": 1, "errors": 1},
                "tried to open a database: sqlite3.connect",
                id="swallowed_in_teardown",
            ),
        ],
    )
    def test_a_module_fixture_that_connects_fails(self, pytester, before, after, outcomes, message):
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
        result.stdout.fnmatch_lines([f"*{message}*"])

    def test_a_refusal_at_module_setup_spares_the_next_module(self, pytester):
        """GIVEN a module fixture refused at setup, WHEN another module runs, THEN it passes."""
        pytester.makeconftest(_INNER_CONFTEST)
        pytester.makepyfile(
            test_a=(
                "import pytest, sqlite3\n\n"
                "@pytest.fixture(scope='module')\ndef database():\n"
                "    sqlite3.connect(':memory:')\n\n"
                "def test_a(database):\n    pass\n"
            ),
            test_b="def test_b():\n    pass\n",
        )

        result = _run(pytester)

        result.assert_outcomes(errors=1, passed=1)

    def test_a_fixture_that_mocks_a_target_is_honoured(self, pytester):
        """GIVEN a fixture that mocks sqlite3.connect, WHEN a test uses it, THEN the mock wins."""
        source = """
            import pytest, sqlite3

            @pytest.fixture
            def fake_connect(monkeypatch):
                monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: "fake")

            def test_uses_the_mock(fake_connect):
                assert sqlite3.connect(":memory:") == "fake"

            def test_the_guard_is_back():
                assert sqlite3.connect.__name__ == "guarded"
            """

        result = _run(pytester, source)

        result.assert_outcomes(passed=2)

    def test_a_refusal_recorded_after_the_check_fails_the_run(self, pytester):
        """GIVEN a refusal swallowed after the teardown check, WHEN the run ends, THEN it fails."""
        source = "def test_passes():\n    pass\n"
        hooks = (
            "import sqlite3\n\n"
            "def pytest_runtest_logreport(report):\n"
            "    if report.when == 'teardown':\n"
            "        try:\n            sqlite3.connect(':memory:')\n"
            "        except BaseException:\n            pass\n"
        )

        result = _run(pytester, source, hooks=hooks)

        assert result.ret == pytest.ExitCode.TESTS_FAILED
        result.stdout.fnmatch_lines(["*outside a test: sqlite3.connect*"])

    def test_a_test_outside_the_unit_tree_may_connect(self, pytester):
        """GIVEN a unit test and another tree, WHEN both run, THEN only the unit one is guarded."""
        for tree in ("a_unit", "b_integration"):
            pytester.mkdir(tree)
        (pytester.path / "a_unit" / "conftest.py").write_text(_INNER_CONFTEST)
        (pytester.path / "a_unit" / "test_a.py").write_text("def test_a():\n    pass\n")
        (pytester.path / "b_integration" / "test_b.py").write_text(
            "import sqlite3\n\ndef test_b():\n    sqlite3.connect(':memory:').close()\n"
        )

        result = _run(pytester, root=pytester.path / "a_unit")

        result.assert_outcomes(passed=2)
