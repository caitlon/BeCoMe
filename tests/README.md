# BeCoMe test suite

Tests for the BeCoMe implementation: 1,730 backend tests, plus 59 end-to-end tests that skip
unless a server and PostgreSQL are up. Coverage is 100% on the core library and 99% overall,
and CI fails the run below 98%.

## Overview

Unit tests cover models, calculators, interpreters, utilities, and API components in isolation. Integration tests validate core results against the original Excel implementation (tolerance: 0.001) and drive the API routes against a database. That database is in-memory SQLite. The engine fixture turns on `PRAGMA foreign_keys`, so the `ondelete` rules declared on the models are enforced here too. A broken CASCADE or a missing RESTRICT goes red on this tier rather than waiting for Postgres. A smaller tier in `tests/integration/api/db/test_postgres_integration.py` runs against a real PostgreSQL and covers what SQLite cannot express. End-to-end tests exercise full API workflows. All tests follow the GIVEN-WHEN-THEN pattern.

## Running tests

```bash
uv run pytest                          # unit + integration (see testpaths)
uv run pytest tests/unit/              # unit tests only
uv run pytest tests/integration/       # integration tests only
uv run pytest tests/e2e/ -n 0          # end-to-end, needs a live server
uv run pytest -v                       # verbose output
uv run pytest -x                       # stop on first failure
uv run pytest -n 0                     # serial, for a readable traceback
```

The suite runs in parallel by default: `-n logical` sits in `addopts`. It reads
`logical` rather than `auto` because xdist resolves `auto` to *physical* cores, and
the CI runner is a hyperthreaded VM with four logical cores over two physical ones,
so `auto` ran the suite on half of it. To use a different worker count on one
machine, set `PYTEST_XDIST_AUTO_NUM_WORKERS`; xdist reads that before it looks at
the hardware, so it overrides `logical` without touching the shared `addopts`.

How many workers is worth measuring rather than guessing, and half the cores is a
tempting guess that does not hold here. On a copy of the tree on local disk, 1,727
tests, two passes agreeing within two seconds: serial 169s, four workers 57s, six
44s, eight 41s, twelve 44s. The curve is flat from six to twelve with a shallow best at eight,
so dropping to six buys nothing. Set `PYTEST_XDIST_AUTO_NUM_WORKERS=8` on a
twelve-core machine and leave `addopts` alone.

**Name the directories, do not pass `tests/`.** xdist hands tests to workers in
collection order, and running the integration tier before the unit tier costs half
again as long: 72s against 48s for the same 1,727 tests on eight workers. Passing
the `tests/` root walks the directories alphabetically, which puts `integration`
first, so `pytest tests/` pays that every time. `testpaths` names the two in the
fast order, which is why a bare `uv run pytest` does not.

Two more things shape these numbers. Nothing is byte-compiled unless you ask:
`uv sync` does not do it, so every worker recompiles all of site-packages on every
run, worth about a tenth of the wall clock (eight workers: 42s against 36s). CI
sets `UV_COMPILE_BYTECODE`, which costs one second there. Locally the same effect
needs `PYTHONPYCACHEPREFIX` pointed somewhere outside the tree, never a plain
`__pycache__`, because this repo lives on iCloud Drive. And a timing taken while
another suite runs on the same machine measures nothing: check `ps` first.

Use `-n 0` in two cases. The first is reading one failure closely, because worker
output interleaves. The second is any small selection: a single file costs more to
distribute than to run, 5.5 seconds against 3.0 for
`tests/unit/models/test_fuzzy_number.py`.

The end-to-end tests need `-n 0`, which `.github/workflows/ci.yml` and
`scripts/ci/e2e-local.sh` both pass. They share one uvicorn process and one
database, so workers queue behind each other until the client's ten-second timeout
in `tests/e2e/conftest.py` starts firing. At twelve workers a quarter of them
failed that way. At four they all passed.

Passing `-n 0` in those two places is not enough on its own, because `addopts`
applies to every invocation: a plain `pytest tests/` sweeps the directory in at
full width. So `pytest_collection_modifyitems` in `tests/e2e/conftest.py` skips
these tests outright whenever the run is distributed. Without it that command paid
ten reconnect attempts per worker with the stack down, and a cascade of timeouts
with it up. Anything new that drives the live stack belongs in this directory, or
needs the same guard.

## Code coverage

```bash
uv run pytest --cov=src --cov-report=term-missing
uv run pytest --cov=src --cov-report=html          # generates htmlcov/
```

Current coverage: 100% on `src/`, and 99% across `src/` and `api/` together. Of the 49 uncovered
lines, 18 sit in the Redis paths: sixteen are the `RedisRevocationStore` error handlers, which
need a Redis that fails rather than one that works, and two are the branch that hands out the
Redis cache. The other 31 are scattered: an in-memory expiry path, a `clear()` test helper, the
`PackageNotFoundError` version fallback, and a handful of parse guards. CI measures the same
number over `tests/unit/` and `tests/integration/` only, because the end-to-end tests drive a
separate uvicorn process that in-process coverage cannot see.

## Test structure

```
tests/
├── unit/
│   ├── models/          # FuzzyTriangleNumber, ExpertOpinion, BeCoMeResult
│   ├── calculators/     # arithmetic mean, median, strategies, compromise
│   ├── interpreters/    # Likert scale interpreter
│   ├── utilities/       # display, formatting, analysis helpers
│   └── api/             # API unit tests
│       ├── auth/            # JWT, password hashing, token blacklist
│       ├── middleware/      # rate limiting, security headers, exceptions
│       ├── schemas/         # request/response validation
│       ├── services/        # business logic (users, projects, opinions)
│       └── utils/           # sanitization
├── integration/
│   ├── test_excel_reference.py   # validates against Excel (3 case studies)
│   ├── test_data_loading.py      # text file parsing
│   └── api/                      # API integration tests
│       ├── auth/            # authentication flows
│       ├── db/              # database models, relationships, cascades
│       └── routes/          # HTTP endpoint integration tests
├── e2e/                 # end-to-end API workflow tests
├── shared/              # test helpers and utilities
└── reference/
    ├── budget_case.py    # 22 experts, expected results
    ├── floods_case.py    # 13 experts, expected results
    └── pendlers_case.py  # 22 experts, Likert scale
```

**Unit tests** (1,215) check individual components in isolation, including API auth, schemas,
services, and middleware. **Integration tests** (512) validate core calculations against Excel
results (tolerance: 0.001) and test API routes with a real database. **End-to-end tests** (59)
exercise complete API workflows including auth, projects, and invitations. **Reference data**
contains expected values from the original Excel implementation.

To regenerate those counts, run `uv run pytest tests/unit/ --collect-only -q` and the same
command for `tests/integration/` and `tests/e2e/`.

## Writing tests

Tests follow GIVEN-WHEN-THEN:

```python
def test_example():
    # GIVEN
    opinions = [ExpertOpinion("E1", FuzzyTriangleNumber(5, 10, 15))]

    # WHEN
    result = calculator.calculate_compromise(opinions)

    # THEN
    assert result.best_compromise.peak == expected_value
```

Each test runs in isolation: no shared state, fresh fixtures, and deterministic outcomes.

## Related documentation

- [Main README](https://docs.becomify.app/): project overview
- [src/README.md](https://docs.becomify.app/dev/core/): implementation details
- [Method description](https://docs.becomify.app/method-description/): mathematical foundation
