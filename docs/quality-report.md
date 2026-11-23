# Code quality report

## Contents

- [Summary](#summary)
- [Running checks](#running-checks)
- [Coverage by module](#coverage-by-module)
- [Test breakdown](#test-breakdown)
- [Mutation testing](#mutation-testing)
    - [Results by module](#results-by-module)
    - [Surviving mutants](#surviving-mutants)
    - [Running](#running)
- [Performance testing](#performance-testing)
- [Production performance](#production-performance)
- [Configuration](#configuration)

## Summary

Measured on 2026-09-30.

| Check | Status | Result |
|-------|--------|--------|
| mypy (strict) | Pass | No errors (22 files in `src/`+`examples/`, 124 in `api/`) |
| ruff check | Pass | No issues |
| ruff format | Pass | All files formatted |
| pytest | Pass | 3266 passed (`testpaths` is unit plus integration; the e2e tier is its own run, `pytest tests/e2e/ -n 0`, and needs a live PostgreSQL) |
| coverage | Pass | 100% on `src/` (164 statements), 99.06% on `src/`+`api/` (6195 statements, 58 uncovered). CI enforces `--cov-fail-under=98` on the full run |

The pytest count assumes `pg_ctl` from PostgreSQL 16 with pgvector on `PATH`. Without `pg_ctl`, 37 tests skip and 3229 pass (coverage 98.60%). With a PostgreSQL that lacks pgvector, 20 skip and 3246 pass (also 98.60%).

## Running checks

```bash
uv run mypy src/ examples/
uv run ruff check .
uv run pytest --cov=src --cov-report=term-missing
```

Or all at once:
```bash
uv run mypy src/ examples/ && uv run ruff check . && uv run pytest --cov=src
```

## Coverage by module

| Module | Statements | Coverage |
|--------|------------|----------|
| calculators/become_calculator.py | 28 | 100% |
| exceptions.py | 4 | 100% |
| interpreters/likert_interpreter.py | 24 | 100% |
| models/become_result.py | 24 | 100% |
| models/expert_opinion.py | 32 | 100% |
| models/fuzzy_number.py | 48 | 100% |
| **Total** | **160** | **100%** |

HTML report: `uv run pytest --cov=src --cov-report=html` generates `htmlcov/index.html`.

## Test breakdown

Unit tests (2611) cover models, calculators, interpreters, utilities, and API components (auth, schemas, services, middleware, logging). Integration tests (655) validate core calculations against Excel reference data for all three case studies and test API routes with a real database. End-to-end tests (59) exercise full API workflows. They skip on a machine without a live PostgreSQL and run in CI. The frontend adds 1237 Vitest tests, which CI holds to coverage thresholds of 98% statements, 95% branches, 97% functions and 98% lines (`frontend/vitest.config.ts`), and 292 Playwright tests in six projects: `chromium`, `firefox` and `webkit` run 88 each, `wcag-audit` 16, `visual-regression` 9 and `docs-screenshots` 3. Edge cases include a single expert, identical opinions, empty lists, and boundary values.

To regenerate these counts, run `uv run pytest tests/unit/ --collect-only -q` for each backend tier, `npx vitest run` in `frontend/`, and `npx playwright test --list`.

Logging has its own two-part guard. `tests/unit/api/test_logging_events.py` asserts that each refusal, external call, and read emits the record it promises, at the level it promises. Several of those tests assert on what is *absent*. A CSRF record must not carry the token it just compared, and a throttle record must not carry the account it throttled. `tests/unit/api/test_logging_pii.py` walks the syntax tree of every module under `api/` and fails on an `extra={...}` field whose name denotes a credential or a raw identifier. The rule in `docs/security.md` therefore does not depend on a reviewer noticing it.

## Mutation testing

Run date: 2026-11-23, against commit `c17652cc`.

Mutation testing measures test suite quality. mutmut introduces small code changes called mutants, replacing `+` with `-` and `<=` with `<`, and swapping constants. It then checks whether the existing tests detect each change. A "killed" mutant means the tests caught the defect. A "survived" mutant means they did not.

| Metric | Value |
|--------|-------|
| Tool | mutmut 3.8.1 |
| Target | `src/` (core library) |
| Tests run against each mutant | `tests/unit/models`, `tests/unit/calculators`, `tests/unit/interpreters`, `tests/integration/test_excel_reference.py`, `tests/integration/test_data_loading.py` |
| Total mutants | 237 |
| Killed | 204 |
| Survived | 33 |
| Timeout | 0 |
| **Raw mutation score** | **86.1%** |

Raw mutation score = killed / (killed + survived + timeout + suspicious + segfault). Only killed and survived mutants occurred in this run.

### Results by module

| Module | Total | Killed | Survived | Kill rate |
|--------|-------|--------|----------|-----------|
| `models.fuzzy_number` | 58 | 56 | 2 | 97% |
| `models.become_result` | 28 | 26 | 2 | 93% |
| `models.expert_opinion` | 23 | 22 | 1 | 96% |
| `calculators.become_calculator` | 52 | 43 | 9 | 83% |
| `interpreters.likert_interpreter` | 76 | 57 | 19 | 75% |

Only the modules that mutmut generated mutants for are listed. The arithmetic of the calculator and the model classes is covered well: every survivor in `become_calculator` and `fuzzy_number` sits in the operation name of an error message, an error message or a hash function, none in a calculation.

### Surviving mutants

Each of the 33 survivors was read with `mutmut show` and sorted by what the change does:

| Category | Count | Example | Excluded from the effective score? |
|----------|-------|---------|-------------|
| Likert recommendation text values | 15 | `"Policy is recommended with minor adjustments"` becomes upper case, lower case or wrapped in `XX` | Yes |
| Operation name in the empty-opinions error message | 9 | `"arithmetic mean"` becomes `None`, upper case or wrapped in `XX` | Yes |
| `__str__` text of `BeCoMeResult` | 2 | `'even'` and `'odd'` wrapped in `XX` | Yes |
| Error message of `FuzzyTriangleNumber.average` | 1 | `"Cannot average empty list of fuzzy numbers"` | Yes |
| Fallback text for a Likert value outside the decision map | 4 | `f"Unknown ({likert_value})"` becomes `None` | No |
| `__hash__` of `ExpertOpinion` and `FuzzyTriangleNumber` | 2 | `hash((...))` becomes `hash(None)` | No |

27 of 33 survivors are excluded from the effective score. They change a string literal that only appears in a recommendation, an error message or a `__str__` output, and no computed result changes. The 15 recommendation strings are returned by the API, but no test asserts the exact wording (the interpreter test checks one keyword, ignoring case) and the UI shows its own translated copy instead. Writing tests that assert the exact wording would add maintenance cost without improving defect detection.

The other 6 change what the code does, and the tests do not check it:

- The two fallback branches in `LikertDecisionInterpreter` (`_get_decision_text` and `_get_recommendation`) are reached only when a custom Likert scale contains a value that is not in the built-in map. The mutants make them return `None` instead of a string. No test uses such a scale.
- The two `__hash__` mutants make every instance hash to the same value. Equal objects still hash equally, so sets and dictionaries stay correct, but they would degrade to linear lookups. No test compares a hash with the hash of the field tuple.

**Effective mutation score** (excluding the 27 string mutants): 204 / (237 − 27) = 204 / 210 = **97.1%**.

### Running

```bash
./scripts/ci/mutmut-run.sh                # full mutation run, then the summary
./scripts/ci/mutmut-run.sh results        # summary from the existing mutants/ output
./scripts/ci/mutmut-run.sh detail         # surviving mutants, grouped by module
./scripts/ci/mutmut-run.sh detail <name>  # the diff of one surviving mutant
```

The summary lists the mutants by status (killed, survived, timeout and the rest) and the mutation score. mutmut keeps its state in the git-ignored `mutants/` directory, and the settings are in `[tool.mutmut]` in `pyproject.toml`. The same modes are available through `./scripts/ci/ci-local.sh mutmut`. `mutmut run` reuses the results in `mutants/`, so after changing tests delete it with `rm -rf mutants/` for a fresh measurement, or rerun one mutant with `uv run mutmut run <name>`.

## Performance testing

Run date: 2026-02-22. The commit it ran against no longer resolves in this repository's history, so the figures below are a point-in-time measurement rather than something you can reproduce exactly.

| Endpoint | Experts | Avg (ms) | Median (ms) | P95 (ms) | P99 (ms) | RPS |
|----------|---------|----------|-------------|----------|----------|-----|
| /api/v1/calculate | 10 | 2.3 | 2 | 4 | 9 | 16.0 |
| /api/v1/calculate | 100 | 2.8 | 2 | 5 | 8 | 9.9 |
| /api/v1/calculate | 1000 | 7.4 | 7 | 12 | 28 | 2.9 |
| /api/v1/health | - | 1.9 | 1 | 3 | 10 | 3.2 |

Environment: macOS (Apple Silicon), Python 3.13, PostgreSQL 16 (Docker), 10 concurrent users, 60s run.
Tool: Locust 2.43.3, the version `uv.lock` resolved on the run date; `pyproject.toml` pins a newer one now. Total requests: 1863, failures: 0.

```bash
# Start API server
SECRET_KEY=test-key TESTING=1 uv run uvicorn api.main:app --port 8000

# Run benchmark (separate terminal); the route needs a signed-in user, so give the
# run a verified account
export BECOME_LOAD_EMAIL=<email> BECOME_LOAD_PASSWORD=<password>
uv run locust -f tests/performance/locustfile.py \
    --host http://localhost:8000 --headless \
    --users 10 --spawn-rate 2 --run-time 60s --csv results
```

## Production performance

Run date: 2026-02-22 | Environment: Railway (Hobby), europe-west4, Cloudflare proxy

| Endpoint | Avg TTFB (ms) | Min (ms) | Max (ms) |
|----------|---------------|----------|----------|
| /api/v1/health | 417 | 222 | 534 |
| /api/v1/calculate (10 experts) | 437 | 210 | 504 |

Measured from Prague (CZ) via Cloudflare edge (PRG) → Railway (europe-west4, NL). TTFB includes network latency (~20ms round-trip), Cloudflare proxy overhead, and TLS negotiation. Actual compute time remains ~2-3ms per request. The difference from local benchmarks is purely network overhead.

## Configuration

mypy runs in strict mode (`pyproject.toml`). ruff enforces pycodestyle, pyflakes, isort, bugbear, naming conventions, pyupgrade, bandit, flake8-simplify, and its own ruff-specific rules. Line length is 100 characters.
