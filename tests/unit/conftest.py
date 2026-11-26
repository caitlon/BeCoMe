"""Unit-tier conftest: a unit test never opens a database.

Unit tests use mocks; a test that needs a database belongs in ``tests/integration``.

The entry points that open a connection are wrapped once, when this file is imported, and stay
wrapped. A wrapper calls the original unless ``_active`` is set, which ``pytest_runtest_protocol``
does for the items under ``tests/unit`` only (under xdist one worker runs both tiers). A fixture
or test that mocks an entry point replaces the wrapper and puts it back, so the mock is honoured.
The protocol of an item includes the setup and teardown of the module, class and session fixtures
it triggers, so those are guarded too. Two things are not guarded: a connection made while pytest
imports or collects a module, and the teardown of the last item of the run. pytest tears down the
session fixtures of every tree in that teardown, so an integration fixture that closes its
database there must not be refused; the guard is off for it, and a unit item that runs last loses
it for its own teardown. A session fixture of a unit item torn down after a last item outside
``tests/unit`` is unguarded for the same reason.

A refusal is recorded, then raised with ``pytest.fail`` (a ``BaseException``, so an ``except
Exception`` cannot swallow it), and surfaced exactly once:

- a refusal that propagates fails its phase, and ``pytest_runtest_makereport`` marks the records
  reported when the phase's exception is that failure;
- a refusal that was swallowed (a thread, an ``except BaseException``) is still unreported when
  ``pytest_runtest_teardown`` returns, after every fixture of the item is torn down, and that
  hook fails the item's teardown, unless the teardown failed on its own;
- ``pytest_sessionfinish`` fails the run for a record neither of them saw.

No record outlives its item, so a refusal at the setup of a module fixture cannot fail the next,
innocent test.
"""

import contextlib
import functools
import inspect
import sqlite3
import sqlite3.dbapi2
from collections.abc import Callable, Generator, Iterator
from pathlib import Path

import pytest

_REFUSAL = (
    "a unit test opened a database connection: unit tests use mocks; "
    "a test that needs a database belongs in tests/integration"
)

_UNIT_ROOT = Path(__file__).parent
_active = False
_refusals: list[dict[str, object]] = []


def _check(label: str) -> None:
    if _active:
        _refusals.append({"entry": label, "reported": False})
        pytest.fail(_REFUSAL, pytrace=False)


def _guard(owner: object, name: str) -> None:
    """Wrap ``owner.name`` so that it refuses to run while a unit item is active.

    :param owner: A module or a class.
    :param name: The attribute to wrap: a function, or a classmethod of a class.
    """
    label = f"{getattr(owner, '__name__', owner)}.{name}"
    raw = vars(owner)[name]
    if isinstance(raw, classmethod):
        function: Callable[..., object] = raw.__func__

        @functools.wraps(function)
        def guarded_classmethod(cls: type, *args: object, **kwargs: object) -> object:
            _check(label)
            return function(cls, *args, **kwargs)

        if inspect.iscoroutinefunction(function):
            inspect.markcoroutinefunction(guarded_classmethod)
        setattr(owner, name, classmethod(guarded_classmethod))
        return

    @functools.wraps(raw)
    def guarded(*args: object, **kwargs: object) -> object:
        _check(label)
        return raw(*args, **kwargs)

    setattr(owner, name, guarded)


def _install() -> None:
    """Guard the pool and the DBAPI drivers.

    ``Engine.connect``, ``Engine.raw_connection``, ``Session`` and ``create_all`` all check a
    connection out of ``Pool.connect`` (``SingletonThreadPool``, the in-memory SQLite pool,
    overrides it), and the DBAPI ``connect`` functions sit below it, so a pool built with its
    own ``creator`` and a driver called directly are refused as well. SQLAlchemy's SQLite
    dialect calls ``sqlite3.dbapi2.connect``, a separate name from ``sqlite3.connect``, and
    ``psycopg.connect`` is a bound method taken from ``Connection.connect`` at import, so each
    of them is wrapped on its own. ``create_engine`` itself is not guarded: settings and config
    tests build engines that never connect.
    """
    owners: list[object] = [sqlite3, sqlite3.dbapi2]
    # The drivers and SQLAlchemy come with the api and assistant extras; the core library's
    # tests run without them, and what is not installed cannot be connected either.
    with contextlib.suppress(ImportError):
        from sqlalchemy.pool import Pool, SingletonThreadPool

        owners += [Pool, SingletonThreadPool]
    with contextlib.suppress(ImportError):
        import psycopg

        owners += [psycopg, psycopg.Connection, psycopg.AsyncConnection]
    with contextlib.suppress(ImportError):
        import psycopg2

        owners.append(psycopg2)
    for owner in owners:
        _guard(owner, "connect")


_install()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None) -> Iterator[None]:
    """Turn the guard on for the whole protocol of an item under ``tests/unit``.

    pytest calls this hook for every item, whichever conftest defines it, so the item's own
    path decides. The previous value is put back, because a test that runs pytest in-process
    nests another protocol inside its own.

    :param item: The item about to run.
    :param nextitem: The item after it, or None.
    :yield: Control to the protocol.
    """
    global _active
    previous = _active
    _active = item.path.is_relative_to(_UNIT_ROOT)
    try:
        return (yield)
    finally:
        _active = previous


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Mark the records as reported when the phase failed with the guard's own refusal.

    The decision reads ``call.excinfo``, not the rendered report: ``--tb=no`` leaves the report
    without text, and the text of an unrelated failure may quote the rule.

    :param item: The running item.
    :param call: The phase that just ran.
    :yield: Control to the report builder.
    :return: The report, unchanged.
    """
    report = yield
    excinfo = call.excinfo
    if _refusals and excinfo is not None and str(excinfo.value) == _REFUSAL:
        for refusal in _refusals:
            refusal["reported"] = True
    return report


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> Iterator[None]:
    """Fail the teardown of an item whose code met a refusal and swallowed the error.

    Code after the ``yield`` runs once every fixture the item finishes, module and session
    fixtures included, is torn down. The records are marked reported even when the teardown
    itself raised, so they cannot fail the next item; that error is then the one reported. For
    the last item of the run (``nextitem`` is None) pytest tears down the session fixtures of
    every tree here and an integration fixture may connect, so the guard is off for this phase.

    :param item: The item being torn down.
    :param nextitem: The item after it, or None.
    :yield: Control to the teardown.
    """
    global _active
    previous = _active
    if nextitem is None:
        _active = False
    try:
        result = yield
    finally:
        _active = previous
        swallowed = sorted({str(r["entry"]) for r in _refusals if not r["reported"]})
        for refusal in _refusals:
            refusal["reported"] = True
    if swallowed:
        pytest.fail(
            f"the unit test tried to open a database: {', '.join(swallowed)}", pytrace=False
        )
    return result


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_sessionfinish(session: pytest.Session) -> Iterator[None]:
    """Fail the run when a refusal was recorded and nothing reported it.

    Same shape as the socket guard in ``tests/conftest.py``: ``shouldfail`` is what an xdist
    worker sends to the controller, its own exit status is not.

    :param session: The finishing session.
    :yield: Control to the other ``pytest_sessionfinish`` hooks.
    """
    missed = sorted({str(r["entry"]) for r in _refusals if not r["reported"]})
    for refusal in _refusals:
        refusal["reported"] = True
    if missed:
        message = f"a unit test tried to open a database outside a test: {', '.join(missed)}"
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        session.shouldfail = message
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(message, red=True)
    return (yield)
