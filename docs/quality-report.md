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

| Check | Status | Result |
|-------|--------|--------|
| mypy (strict) | Pass | No errors (24 files in `src/`+`examples/`, 92 in `api/`) |
| ruff check | Pass | No issues |
| ruff format | Pass | All files formatted |
| pytest | Pass | 1730 passed (`testpaths` is unit plus integration; the e2e tier is its own run, `pytest tests/e2e/ -n 0`, and needs a live PostgreSQL) |
| coverage | Pass | 100% on `src/` (197 statements), 98.86% on `src/`+`api/` (4307 statements, 49 uncovered). CI enforces `--cov-fail-under=98` on the full run |

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
| calculators/base_calculator.py | 12 | 100% |
| calculators/become_calculator.py | 28 | 100% |
| calculators/median_strategies.py | 14 | 100% |
| exceptions.py | 8 | 100% |
| interpreters/likert_interpreter.py | 24 | 100% |
| models/become_result.py | 24 | 100% |
| models/expert_opinion.py | 36 | 100% |
| models/fuzzy_number.py | 51 | 100% |
| **Total** | **197** | **100%** |

HTML report: `uv run pytest --cov=src --cov-report=html` generates `htmlcov/index.html`.

## Test breakdown

Unit tests (1215) cover models, calculators, interpreters, utilities, and API components (auth, schemas, services, middleware, logging). Integration tests (512) validate core calculations against Excel reference data for all three case studies and test API routes with a real database. End-to-end tests (59) exercise full API workflows. They skip on a machine without a live PostgreSQL and run in CI. The frontend adds 1027 Vitest tests, and 229 Playwright runs across five browser projects. Edge cases include a single expert, identical opinions, empty lists, and boundary values.

To regenerate these counts, run `uv run pytest tests/unit/ --collect-only -q` for each backend tier, `npx vitest run` in `frontend/`, and `npx playwright test --list`.

Logging has its own two-part guard. `tests/unit/api/test_logging_events.py` asserts that each refusal, external call, and read emits the record it promises, at the level it promises. Several of those tests assert on what is *absent*. A CSRF record must not carry the token it just compared, and a throttle record must not carry the account it throttled. `tests/unit/api/test_logging_pii.py` walks the syntax tree of every module under `api/` and fails on an `extra={...}` field whose name denotes a credential or a raw identifier. The rule in `docs/security.md` therefore does not depend on a reviewer noticing it.

## Mutation testing

Run date: 2026-02-22. The commit it ran against no longer resolves in this repository's history, so the figures below are a point-in-time measurement rather than something you can reproduce exactly. Rerun the commands to refresh them.

Mutation testing measures test suite quality. mutmut introduces small code changes called mutants, replacing `+` with `-` and `<=` with `<`, and swapping constants. It then checks whether the existing tests detect each change. A "killed" mutant means the tests caught the defect. A "survived" mutant means they did not.

| Metric | Value |
|--------|-------|
| Tool | mutmut 2.5.1, the version `uv.lock` resolved on the run date; the project now pins 3.6.0 |
| Target | `src/` (core library) |
| Total mutants | 170 |
| Killed | 120 |
| Survived | 50 |
| Timeout | 0 |
| **Raw mutation score** | **70.6%** |

Raw mutation score = killed / (killed + survived).

### Results by module

| File | Total | Killed | Survived | Kill rate |
|------|-------|--------|----------|-----------|
| base_calculator.py | 4 | 4 | 0 | 100% |
| median_strategies.py | 9 | 9 | 0 | 100% |
| become_calculator.py | 18 | 14 | 4 | 78% |
| fuzzy_number.py | 39 | 28 | 11 | 72% |
| expert_opinion.py | 19 | 14 | 5 | 74% |
| likert_interpreter.py | 41 | 34 | 7 | 83% |
| become_result.py | 40 | 17 | 23 | 43% |

Modules with core computational logic (`base_calculator`, `median_strategies`) have a 100% kill rate: the test suite detects every arithmetic and sorting mutation.

### Surviving mutants

50 surviving mutants by category:

| Category | Count | Example | Equivalent? |
|----------|-------|---------|-------------|
| Pydantic `Field(description=...)` strings | 23 | `description="Best compromise (ΓΩMean)..."` | Yes |
| `__repr__` / `__str__` format strings | 10 | `f"FuzzyTriangleNumber(lower_bound=..."` | Yes |
| Error message strings | 7 | `f"Cannot calculate {operation}..."` | Yes |
| Likert decision map text values | 6 | `"Policy is recommended with minor adjustments"` | Yes |
| Class metadata (`__slots__`, decorators) | 4 | `__slots__ = (...)`, `@staticmethod` | No |

46 of 50 survivors are equivalent mutants: changes to string literals in error messages, OpenAPI descriptions, and `repr()` output that do not alter what the code computes. Writing tests to assert exact error message text would add maintenance cost without improving defect detection. The remaining 4 mutants modify class metadata (`__slots__` tuples, `@staticmethod` decorators). Those are structurally harmless but not strictly equivalent.

**Effective mutation score** (excluding 46 equivalent string mutants): 120 / (170 − 46) = **96.8%**.

### Running

```bash
./scripts/ci/mutmut-run.sh          # full mutation run
./scripts/ci/mutmut-run.sh results  # view summary from cache
./scripts/ci/mutmut-run.sh detail   # list surviving mutants by file
```

## Performance testing

Run date: 2026-02-22, on the same unresolvable commit as the mutation run above.

| Endpoint | Experts | Avg (ms) | Median (ms) | P95 (ms) | P99 (ms) | RPS |
|----------|---------|----------|-------------|----------|----------|-----|
| /api/v1/calculate | 10 | 2.3 | 2 | 4 | 9 | 16.0 |
| /api/v1/calculate | 100 | 2.8 | 2 | 5 | 8 | 9.9 |
| /api/v1/calculate | 1000 | 7.4 | 7 | 12 | 28 | 2.9 |
| /api/v1/health | - | 1.9 | 1 | 3 | 10 | 3.2 |

Environment: macOS (Apple Silicon), Python 3.13, PostgreSQL 16 (Docker), 10 concurrent users, 60s run.
Tool: Locust 2.43.3, the version `uv.lock` resolved on the run date. The project now pins 2.46.2. Total requests: 1863, failures: 0.

```bash
# Start API server
SECRET_KEY=test-key TESTING=1 uv run uvicorn api.main:app --port 8000

# Run benchmark (separate terminal)
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
