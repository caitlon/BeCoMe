# BeCoMe test suite

Tests for the BeCoMe implementation: 3,266 backend tests, plus 59 end-to-end tests that skip
unless a server and PostgreSQL are up. Coverage is 100% on the core library and 99% overall,
and CI fails the run below 98%.

## Contents

- [Overview](#overview)
- [Running tests](#running-tests)
- [Code coverage](#code-coverage)
- [Test structure](#test-structure)
- [Frontend tests](#frontend-tests)
- [Writing tests](#writing-tests)
- [Keeping tests on this machine](#keeping-tests-on-this-machine)
- [Related documentation](#related-documentation)

## Overview

Unit tests cover models, calculators, interpreters, utilities, and API components in isolation. A unit test never opens a database, in a test or in its fixtures: `tests/unit/conftest.py` fails a connection checked out of a SQLAlchemy pool or opened with `sqlite3`, `psycopg` or `psycopg2`, and fails the test at teardown when the code under test swallowed the refusal. A unit test may still build an engine, which does not connect. One that needs a database goes in `tests/integration`. Integration tests validate core results against the original Excel implementation (tolerance: 0.001) and drive the API routes against a database. That database is in-memory SQLite. The engine fixture turns on `PRAGMA foreign_keys`, so the `ondelete` rules declared on the models are enforced here too. A broken CASCADE or a missing RESTRICT goes red on this tier rather than waiting for Postgres. A smaller tier runs against a real PostgreSQL and covers what SQLite cannot express: `tests/integration/api/db/test_postgres_integration.py` and `test_migrations.py` beside it, and `test_assistant_store.py`, `test_assistant_pipeline.py` and `test_assistant_retrieval.py` in `tests/integration/api/`, which also need pgvector. All five skip when `pg_ctl` is not on `PATH`. End-to-end tests exercise full API workflows. All tests follow the GIVEN-WHEN-THEN pattern.

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
sets `UV_COMPILE_BYTECODE`, which costs one second there. Locally the cache Python
writes on the first run does the same job, and `PYTHONPYCACHEPREFIX` decides where
it lands: point it outside the tree and the checkout keeps no `__pycache__` of its
own. It buys no speed on a fresh worktree -- the prefix mirrors the absolute source
path, so a new one starts cold either way. And a timing taken while another suite
runs on the same machine measures nothing: check `ps` first.

Use `-n 0` in two cases. The first is reading one failure closely, because worker
output interleaves. The second is any small selection: a single file costs more to
distribute than to run, 5.5 seconds against 3.0 for
`tests/unit/models/test_fuzzy_number.py`.

The end-to-end tests need `-n 0`, which `.github/workflows/ci.yml` and
`scripts/ci/e2e-local.sh` both pass. They share one uvicorn process and one
database, so workers queue behind each other until the client's ten-second timeout
in `tests/e2e/conftest.py` starts firing. At twelve workers a quarter of them
failed that way. At four they all passed.

`scripts/ci/e2e-local.sh` takes a mode: `all`, `backend`, `playwright`, `visual`, or
`docs`. The last one is not a test. It runs the `docs-screenshots` Playwright project,
which photographs the app into `docs/user/img/` for the documentation site, and it is
deliberately outside `all` because it writes files rather than checking anything.

Two things about that mode are worth knowing before changing it. It runs
`alembic upgrade head` first, which the other modes do not: the example project it
photographs only seeds when the demo expert pool exists, and that pool is created by a
migration while the test profile builds its schema with `create_all`. Without the
migration the seed is skipped, and the failure reads as a missing link on an empty
project list rather than as a missing pool. And its screenshots are not the ones in
`visual-regression.spec.ts-snapshots`: those are byte-compared baselines rendered on
Linux, these are illustrations, and keeping them apart stops the documentation from
dictating what the regression suite checks.

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

Current coverage: 100% on `src/`, and 99% across `src/` and `api/` together. Of the 58
uncovered lines, 18 sit in the Redis paths: fourteen are the `RedisRevocationStore` error
handlers, which need a Redis that fails rather than one that works, two are the retry in
`rotate_session` when a watched key changes under it, and two are the branch that hands out
the Redis cache. The other 40 are the legacy-refresh-token branch in `api/routes/auth.py`
(5 lines, for a token minted before sessions existed); the two fail-closed handlers in
`api/auth/jwt.py` that reject a token when the revocation store is down (4); the `clear()`
test helper (5) and two in-memory expiry paths (4), one for a revoked session and one for a
cached user past their lifetime; the `PackageNotFoundError` version fallback (2); three
`RuntimeError` guards in `api/assistant/rag/retrieval.py` that cannot be reached (3); parse
guards in `login_throttle.py` and `body_size.py` (4); and 13 single-line guards and branches
spread over nine modules. CI measures the same number over `tests/unit/` and
`tests/integration/` only, because the end-to-end tests drive a separate uvicorn process that
in-process coverage cannot see.

## Test structure

```
tests/
├── unit/
│   ├── conftest.py      # fails a unit test that opens a database connection
│   ├── strategies.py    # Hypothesis strategies for the property tests
│   ├── models/          # FuzzyTriangleNumber, ExpertOpinion, BeCoMeResult
│   ├── calculators/     # arithmetic mean, median, centroid sort, compromise
│   ├── interpreters/    # Likert scale interpreter
│   ├── utilities/       # display, formatting, analysis helpers
│   ├── docs/            # the table-of-contents generator for the docs
│   └── api/             # API unit tests
│       ├── assistant/       # assistant client, rate limit, ingest, views
│       │   ├── agent/           # prompt, tools, answer checks, tracing
│       │   └── rag/             # chunkers, corpus, loaders, retrieval, store
│       ├── auth/            # JWT, password hashing, token blacklist
│       ├── data/            # example project seeding
│       ├── db/              # example columns, error text
│       ├── middleware/      # rate limiting, security headers, exceptions
│       ├── schemas/         # request/response validation
│       ├── services/        # business logic (users, projects, opinions)
│       └── utils/           # sanitization
├── integration/
│   ├── test_excel_reference.py   # validates against Excel (3 case studies)
│   ├── test_data_loading.py      # text file parsing
│   ├── test_frontend_*.py        # frontend build args, CSP, case-study numbers
│   ├── scripts/assistant/        # the evaluation fixture seeder
│   └── api/                      # API integration tests
│       ├── test_assistant_*.py   # assistant chat, client, config and RAG
│       ├── auth/            # authentication flows
│       ├── db/              # database models, relationships, cascades, migrations
│       ├── middleware/      # request logging wiring
│       ├── routes/          # HTTP endpoint integration tests
│       └── services/        # user cache, account tokens, the example project
├── e2e/                 # end-to-end API workflow tests
├── performance/         # Locust load test, not collected by pytest
├── shared/
│   ├── assistant_fakes.py    # scripted chat model for the assistant tests
│   ├── helpers.py            # constants and helpers used across tiers
│   ├── pdf_inspection.py     # reads colours back out of a rendered PDF
│   ├── resp_stub.py          # loopback Redis stub that answers like a read-only replica
│   └── sentry_capture.py     # starts Sentry against a transport that keeps the envelopes
└── reference/
    ├── _case_factory.py  # builds a reference case from its data file
    ├── budget_case.py    # 22 experts, expected results
    ├── floods_case.py    # 13 experts, expected results
    └── pendlers_case.py  # 22 experts, Likert scale
```

**Unit tests** (2,611) check individual components in isolation, including API auth, schemas,
services, and middleware. **Integration tests** (655) validate core calculations against Excel
results (tolerance: 0.001) and test API routes with a real database. **End-to-end tests** (59)
exercise complete API workflows including auth, projects, and invitations. **Reference data**
contains expected values from the original Excel implementation.

To regenerate those counts, run `uv run pytest tests/unit/ --collect-only -q` and the same
command for `tests/integration/` and `tests/e2e/`.

## Frontend tests

The frontend has its own suites, run with npm from `frontend/`. They are not part of
`uv run pytest`.

- **Vitest unit tests** live in `frontend/tests`: 1,237 tests in 95 files. Seven directories
  hold them (`components`, `contexts`, `data`, `hooks`, `i18n`, `lib` and `pages`), and
  `App.test.tsx` sits at the top level. `factories` and `mocks` hold support code rather than
  tests, as do `setup.ts` and `utils.tsx`.
- **Playwright end-to-end specs** live in `frontend/e2e`: 292 tests in six projects from
  `frontend/playwright.config.ts`. `chromium`, `firefox` and `webkit` run the same 88
  functional specs, `wcag-audit` runs 16 accessibility checks, `visual-regression` 9
  screenshot comparisons, and `docs-screenshots` 3 that photograph the app for the
  documentation site.

```bash
npm run test                            # vitest in watch mode
npm run test:run                        # vitest, a single run
npm run test:coverage                   # vitest, a single run with the coverage gate
npm run test:e2e -- --project=chromium  # one Playwright project
```

Playwright needs a live API and database, so run it through `./scripts/ci/e2e-local.sh`
(`playwright` for the three browsers, `visual` for the regression baselines, `docs` for the
screenshots) or name a `--project=`. A bare `npm run test:e2e` runs every project, and
`docs-screenshots` would overwrite the tracked images in `docs/user/img/`.

The coverage gate in `frontend/vitest.config.ts` fails the run below 98% statements, 95%
branches, 97% functions and 98% lines. CI runs it through `test:coverage`, but
`./scripts/ci/ci-local.sh fast` runs `test:run`, which has no gate, so run
`npm run test:coverage` before pushing a frontend change.

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

## Keeping tests on this machine

No test may reach another host, and no unit test opens a database. The root `tests/conftest.py` enforces the first with the environment file and the socket guard; `tests/unit/conftest.py` enforces the second.

**The environment.** `tests/test.env` lists the variables every run starts from: the test profile, the console mail sender, blank keys and hosts for Sentry, Better Stack, the bucket, Redis, LangSmith and the hosted model, blank `MIGRATION_DATABASE_URL` and `ASSISTANT_VECTOR_DB_URL`, and the assistant's answer, LLM and embedding providers set to `local` with their base URLs on `127.0.0.1`. The file is read before anything imports `api`, and a process variable beats `.env`, so a developer's `.env` cannot select a live service. A blank value overrides `.env`; a missing one would not. `scripts/ci/test-env.sh` exports the same file for the scripts that start the tests or the API, and the CI jobs append it to `$GITHUB_ENV`. A test of a default that the file blanks removes the variable itself (`monkeypatch.delenv`) and runs from `tmp_path`, as `tests/unit/api/test_config.py` does.

**The socket guard.** `tests/network_guard.py` patches the socket calls that connect, send a datagram or look up a name. Loopback addresses and the names `localhost` and `localhost.` (the only ones every resolver answers locally), the unspecified addresses (`0.0.0.0`, `::`), unix sockets, `bind` and `listen` pass. This machine's own host name does not, because resolving it goes to the system resolver and can send a real DNS query: `socket.getfqdn()` and `email.utils.make_msgid()` are refused, and a test that needs them mocks them. A reverse lookup passes only for what every hosts file maps: `gethostbyaddr` for `localhost`, `127.0.0.1` and `::1`, `getnameinfo` without `NI_NUMERICHOST` for `127.0.0.1` and `::1`, because the resolver may ask an outside DNS server about any other address. Anything else raises `NetworkBlockedError` and is recorded, because several clients swallow their own errors: a test during which a refusal was recorded fails at teardown with `the test tried to leave the machine: <operation> to <host>`, whatever the code did with the error. A refusal swallowed outside any test, in a module or session fixture or its teardown, fails the run when the session ends (exit code 1, or 2 under xdist). The database drivers open their sockets in C, below the guard, so a `DATABASE_URL` (the one an E2E or DAST run sets; `tests/test.env` blanks the other two database URLs) with a host outside this machine, in the authority or in a `host` or `hostaddr` query parameter, or with a `service` parameter, is refused at start-up instead. libpq fills a host the URL leaves out from `PGHOST` and `PGHOSTADDR`, so a non-local value of either stops the run whatever the URL says, and so does a set `PGSERVICE`, because its service file cannot be read here. The guard does not cover subprocesses a test starts, C code other than libpq, or a module that bound `socket` functions before the root conftest ran.

- A test that needs a server starts a stub on `127.0.0.1`, bound to port 0 so the system picks a free port.
- A test that reaches an outside client (a mail provider, LangSmith, a model host) mocks it. A real client object may be built, but its transport must not connect, as `_offline_client` in `tests/unit/api/assistant/agent/test_tracing.py` does.
- `NETWORK_GUARD_LOG=<file>` appends every refused attempt to that file as a JSON line with the test, the operation and the target, which is the quick way to find the test behind a failure.
- `tests/unit/test_network_guard.py` triggers the guard on purpose and removes what it recorded.
- The frontend unit tests have a guard of their own over `fetch`, `XMLHttpRequest`, `WebSocket` and `navigator.sendBeacon` (`frontend/tests/support/network-guard.ts`, installed by `frontend/tests/setup.ts`). A test mocks a request with `vi.stubGlobal('fetch', vi.fn(...))` (`vi.spyOn(navigator, 'sendBeacon').mockReturnValue(true)` for sendBeacon); see "Testing" in `frontend/README.md`.

**The database guard.** `tests/unit/conftest.py` wraps `Pool.connect` (so `Engine.connect`, `raw_connection`, `Session` and `create_all` are caught), `sqlite3.connect`, `sqlite3.dbapi2.connect`, `psycopg.connect`, `psycopg.Connection.connect`, `psycopg.AsyncConnection.connect` and `psycopg2.connect` once, when the file is imported. While an item under `tests/unit` runs, from the setup of its fixtures to their teardown, a wrapper fails with "unit tests use mocks; a test that needs a database belongs in tests/integration"; for every other item it calls the original, which keeps an xdist worker that mixes both tiers correct. The wrappers are never undone, so a fixture or test that mocks one of these functions replaces the wrapper and the mock is honoured. A refusal the code swallowed (a thread, an `except BaseException`) fails the teardown of the item that met it, naming the entry points, and one recorded after that check fails the run when the session ends. Two things are outside it: a connection made while pytest imports or collects a module, and the teardown of the last item of the run, where the guard is off because pytest tears down the session fixtures of every tree there and an integration fixture may close its database (a session fixture of a unit item torn down after a last item outside `tests/unit` is unguarded for the same reason). `create_engine` is not guarded, because settings and config tests build engines without connecting; `tests/unit/test_database_guard.py` shows both sides. A unit test that needs a connection moves to `tests/integration`, where the in-memory SQLite engine fixtures live.

## Related documentation

- [Main README](https://docs.becomify.app/): project overview
- [Core library](https://docs.becomify.app/dev/core/): implementation details
- [Method description](https://docs.becomify.app/method-description/): mathematical foundation
