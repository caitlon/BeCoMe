"""Unit-tier conftest: a unit test never opens a database.

Unit tests use mocks; a test that needs a database belongs in ``tests/integration``. A hook
defined in this file runs only for the items under ``tests/unit``. That matters under xdist,
where one worker runs unit and integration tests in the same process: the patches are on
while a unit item sets up, runs and tears down, and undone before an item of any tier starts.
"""

import importlib
import sqlite3
import sqlite3.dbapi2
from collections.abc import Iterator
from typing import NoReturn

import pytest
from sqlalchemy.pool import Pool, SingletonThreadPool

_REFUSAL = (
    "a unit test opened a database connection: unit tests use mocks; "
    "a test that needs a database belongs in tests/integration"
)

# Every refusal since the last check, by entry point, so one swallowed in a thread or by an
# ``except BaseException`` still fails the test that was running.
_refusals: list[str] = []


def _entry_points() -> list[tuple[object, str]]:
    """Return the places a database connection is opened: the pool and the DBAPI drivers."""
    points: list[tuple[object, str]] = [
        (Pool, "connect"),
        (SingletonThreadPool, "connect"),
        (sqlite3, "connect"),
        (sqlite3.dbapi2, "connect"),
    ]
    for name in ("psycopg", "psycopg2"):
        try:
            points.append((importlib.import_module(name), "connect"))
        except ImportError:
            continue
    return points


_ENTRY_POINTS = _entry_points()


def _refuser(label: str) -> object:
    def refuse(*args: object, **kwargs: object) -> NoReturn:
        _refusals.append(label)
        pytest.fail(_REFUSAL, pytrace=False)

    return refuse


@pytest.hookimpl(wrapper=True)
def _refuse_database_in_phase() -> Iterator[None]:
    """Refuse every database connection while one phase of a unit test runs.

    ``Engine.connect``, ``Engine.raw_connection``, ``Session`` and ``create_all`` all check a
    connection out of ``Pool.connect`` (``SingletonThreadPool``, the in-memory SQLite pool,
    overrides it), and the DBAPI ``connect`` functions sit below it, so a pool built with its
    own ``creator`` and a driver called directly are refused as well. SQLAlchemy's SQLite
    dialect calls ``sqlite3.dbapi2.connect``, a separate name from ``sqlite3.connect``.
    ``create_engine`` itself is not: settings and config tests build engines that never
    connect. ``pytest.fail`` raises a ``BaseException``, so an ``except Exception`` in the code
    under test cannot swallow the refusal.

    The setup phase of the first test of a module runs its module and class fixtures, and the
    teardown phase of the last one finishes them, so the three phase hooks below cover those
    fixtures too. A hook in this file runs for the items under ``tests/unit`` only; the
    ``pytest_runtest_protocol`` hook would run for every item.

    :yield: Control to the phase.
    """
    with pytest.MonkeyPatch.context() as patch:
        for target, name in _ENTRY_POINTS:
            label = f"{getattr(target, '__name__', target)}.{name}"
            patch.setattr(target, name, _refuser(label))
        return (yield)


pytest_runtest_setup = pytest_runtest_call = pytest_runtest_teardown = _refuse_database_in_phase


@pytest.fixture(autouse=True)
def _no_swallowed_database_refusal() -> Iterator[None]:
    """Fail a test whose code met a refused connection and swallowed the error.

    :yield: Control to the test.
    """
    yield
    refused = sorted(set(_refusals))
    _refusals.clear()
    if refused:
        pytest.fail(f"the unit test tried to open a database: {', '.join(refused)}", pytrace=False)
