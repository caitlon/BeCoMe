"""Root conftest: keeps the whole suite on this machine.

pytest loads this file before any other conftest and before collecting a single test
module, in the controller and in every xdist worker, so nothing here may import ``api``.

Two layers. The environment in ``tests/test.env`` is pinned first: ``Settings`` reads the
repository's ``.env``, which on a developer machine can name a live mail provider, a
tracing key or a model host, and a process variable beats every dotenv file. Then the
socket guard refuses whatever still tries to leave the machine
(``tests/network_guard.py``), and a test that met a refusal fails even when the client
swallowed the error. A refusal swallowed outside any test (a module or session fixture,
its teardown) fails the run when the session ends.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests import network_guard

_TEST_ENV = Path(__file__).with_name("test.env")

# Read by the LangSmith library from the process environment only, never from .env, so
# removing them is enough, and a blank endpoint is not a value the library should see.
_REMOVED = (
    "LANGSMITH_API_KEY",
    "LANGSMITH_ENDPOINT",
    "LANGSMITH_PROJECT",
    "LANGCHAIN_API_KEY",
    "LANGCHAIN_ENDPOINT",
    "LANGCHAIN_PROJECT",
)

# The database drivers open their sockets in C (libpq), below the socket guard, so a
# database URL is checked here instead. The E2E and DAST runs pass their own local URL.
_DATABASE_URLS = ("DATABASE_URL", "MIGRATION_DATABASE_URL", "ASSISTANT_VECTOR_DB_URL")


def read_test_env() -> dict[str, str]:
    """Parse the ``KEY=VALUE`` lines of the shared test environment.

    :return: Each variable and its value, blank values included.
    """
    values: dict[str, str] = {}
    for line in _TEST_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            name, _, value = line.partition("=")
            values[name.strip()] = value.strip()
    return values


def _pin_environment() -> None:
    os.environ.update(read_test_env())
    for name in _REMOVED:
        os.environ.pop(name, None)
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    # A default, not forced: the E2E and DAST runs pass their own local URL. Each is set in
    # the process, so a remote URL in .env never applies.
    os.environ.setdefault("DATABASE_URL", "sqlite://")
    for name in _DATABASE_URLS:
        host = network_guard.remote_database_host(os.environ.get(name, ""))
        if host is not None:
            raise RuntimeError(f"{name} must point at this machine in tests, not {host!r}")


_pin_environment()
network_guard.install()


@pytest.fixture(autouse=True)
def _no_swallowed_network_attempt(request: pytest.FixtureRequest) -> Iterator[None]:
    """Fail a test whose code met a refused socket and swallowed the error.

    An attempt made by another test (a background thread outlives its test) is named
    with the test it was recorded under.

    :param request: The running test.
    :yield: Control to the test.
    """
    seen = len(network_guard.attempts)
    yield
    found: dict[str, str] = {}
    for attempt in network_guard.attempts[seen:]:
        owner = attempt["test"].rpartition(" (")[0] or attempt["test"]
        label = f"{attempt['operation']} to {attempt['target']}"
        if owner != request.node.nodeid:
            label += f" (first recorded under {owner})"
        found.setdefault(label, owner)
    for attempt in network_guard.attempts[seen:]:
        attempt["reported"] = True
    if found:
        targets = ", ".join(sorted(found))
        pytest.fail(f"the test tried to leave the machine: {targets}", pytrace=False)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_sessionfinish(session: pytest.Session) -> Iterator[None]:
    """Fail the run when a refusal was recorded and no test reported it.

    A module or session fixture is set up before the per-test fixture takes its snapshot,
    so a refusal it swallows never reaches ``_no_swallowed_network_attempt``. ``shouldfail``
    is what an xdist worker sends to the controller: its own exit status is not.

    :param session: The finishing session.
    :yield: Control to the other ``pytest_sessionfinish`` hooks.
    """
    missed = [a for a in network_guard.attempts if not a.get("reported")]
    if missed:
        targets = ", ".join(sorted({f"{a['operation']} to {a['target']}" for a in missed}))
        message = f"the run tried to leave the machine outside a test: {targets}"
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        session.shouldfail = message
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(message, red=True)
    return (yield)
