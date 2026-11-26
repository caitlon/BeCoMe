"""Root conftest: every test run starts from the same safe environment.

pytest loads this file before any other conftest and before collecting a single test
module, in the controller and in every xdist worker, so nothing here may import ``api``.

The environment in ``tests/test.env`` is pinned here: ``Settings`` reads the repository's
``.env``, which on a developer machine can name a live mail provider, a tracing key or a
model host, and a process variable beats every dotenv file.
"""

import os
from pathlib import Path

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
    # Defaults, not forced: the E2E and DAST runs pass their own local URLs. Each is set
    # in the process, so a database URL in .env never applies.
    os.environ.setdefault("DATABASE_URL", "sqlite://")


_pin_environment()
