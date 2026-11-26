"""Unit-tier conftest: a unit test never opens a database.

Unit tests use mocks; a test that needs a database belongs in ``tests/integration``. The
guard is an autouse fixture, and a fixture defined in this file applies only to the tests
under ``tests/unit``. That matters under xdist, where one worker runs unit and integration
tests in the same process: the patch is on while a unit test runs and undone before the
next test of any tier starts.
"""

from collections.abc import Iterator
from typing import NoReturn

import pytest
from sqlalchemy.engine import Engine

_REFUSAL = (
    "a unit test opened a database connection: unit tests use mocks; "
    "a test that needs a database belongs in tests/integration"
)


def _refuse_connection(*args: object, **kwargs: object) -> NoReturn:
    pytest.fail(_REFUSAL, pytrace=False)


@pytest.fixture(autouse=True)
def _unit_tests_open_no_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail a unit test that connects a SQLAlchemy engine.

    ``Session`` and ``create_all`` reach the database through ``Engine.connect``, and the
    pool hands out raw connections through ``Engine.raw_connection``, so both are refused.
    ``create_engine`` itself is not: settings and config tests build engines that never
    connect. ``pytest.fail`` raises a ``BaseException``, so an ``except Exception`` in the
    code under test cannot swallow the refusal.

    :param monkeypatch: Restores both methods when the test ends.
    :yield: Control to the test.
    """
    monkeypatch.setattr(Engine, "connect", _refuse_connection)
    monkeypatch.setattr(Engine, "raw_connection", _refuse_connection)
    yield
