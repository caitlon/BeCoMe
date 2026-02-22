# Code Quality Report

## Summary

| Check | Status | Result |
|-------|--------|--------|
| mypy (strict) | Pass | No errors in 32 files |
| ruff check | Pass | No issues |
| ruff format | Pass | All files formatted |
| pytest | Pass | 187 tests passed |
| coverage | Pass | 100% on `src/` |

## Running Checks

```bash
uv run mypy src/ examples/
uv run ruff check .
uv run pytest --cov=src --cov-report=term-missing
```

Or all at once:
```bash
uv run mypy src/ examples/ && uv run ruff check . && uv run pytest --cov=src
```

## Coverage by Module

| Module | Statements | Coverage |
|--------|------------|----------|
| calculators/base_calculator.py | 12 | 100% |
| calculators/become_calculator.py | 31 | 100% |
| calculators/median_strategies.py | 20 | 100% |
| exceptions.py | 8 | 100% |
| interpreters/likert_interpreter.py | 24 | 100% |
| models/become_result.py | 24 | 100% |
| models/expert_opinion.py | 36 | 100% |
| models/fuzzy_number.py | 46 | 100% |
| **Total** | **201** | **100%** |

HTML report: `uv run pytest --cov=src --cov-report=html` generates `htmlcov/index.html`.

## Test Breakdown

Unit tests cover models (fuzzy numbers, expert opinions, results) and calculators (mean, median, compromise). Integration tests validate against Excel reference data for all three case studies — budget, floods, pendlers. Edge cases include single expert, identical opinions, empty lists, and boundary values.

## Mutation Testing

Run date: 2026-02-22 | Commit: ae7fd59

Mutation testing measures test suite quality: mutmut introduces small code changes (mutants) — replacing `+` with `-`, `<=` with `<`, swapping constants — and checks whether existing tests detect each change. A "killed" mutant means the tests caught the defect; a "survived" mutant means they did not.

| Metric | Value |
|--------|-------|
| Tool | mutmut 2.5.1 |
| Target | `src/` (core library) |
| Total mutants | 170 |
| Killed | 120 |
| Survived | 50 |
| Timeout | 0 |
| **Raw mutation score** | **70.6%** |

Raw mutation score = killed / (killed + survived).

### Results by Module

| File | Total | Killed | Survived | Kill rate |
|------|-------|--------|----------|-----------|
| base_calculator.py | 4 | 4 | 0 | 100% |
| median_strategies.py | 9 | 9 | 0 | 100% |
| become_calculator.py | 18 | 14 | 4 | 78% |
| fuzzy_number.py | 39 | 28 | 11 | 72% |
| expert_opinion.py | 19 | 14 | 5 | 74% |
| likert_interpreter.py | 41 | 34 | 7 | 83% |
| become_result.py | 40 | 17 | 23 | 43% |

Modules with core computational logic (`base_calculator`, `median_strategies`) have 100% kill rate — every arithmetic and sorting mutation is detected by the test suite.

### Surviving Mutants Analysis

50 surviving mutants by category:

| Category | Count | Example | Equivalent? |
|----------|-------|---------|-------------|
| Pydantic `Field(description=...)` strings | 23 | `description="Best compromise (ΓΩMean)..."` | Yes |
| `__repr__` / `__str__` format strings | 10 | `f"FuzzyTriangleNumber(lower_bound=..."` | Yes |
| Error message strings | 7 | `f"Cannot calculate {operation}..."` | Yes |
| Likert decision map text values | 6 | `"Policy is recommended with minor adjustments"` | Yes |
| Class metadata (`__slots__`, decorators) | 4 | `__slots__ = (...)`, `@staticmethod` | No |

46 of 50 survivors are equivalent mutants: changes to string literals in error messages, OpenAPI descriptions, and `repr()` output that do not alter what the code computes. Writing tests to assert exact error message text would add maintenance cost without improving defect detection. The remaining 4 mutants modify class metadata (`__slots__` tuples, `@staticmethod` decorators) — structurally harmless but not strictly equivalent.

**Effective mutation score** (excluding 46 equivalent string mutants): 120 / (170 − 46) = **96.8%**.

### Running

```bash
./scripts/mutmut-run.sh          # full mutation run
./scripts/mutmut-run.sh results  # view summary from cache
./scripts/mutmut-run.sh detail   # list surviving mutants by file
```

## Performance Testing

Run date: 2026-02-22 | Commit: ae7fd59

| Endpoint | Experts | Avg (ms) | Median (ms) | P95 (ms) | P99 (ms) | RPS |
|----------|---------|----------|-------------|----------|----------|-----|
| /api/v1/calculate | 10 | 2.3 | 2 | 4 | 9 | 16.0 |
| /api/v1/calculate | 100 | 2.8 | 2 | 5 | 8 | 9.9 |
| /api/v1/calculate | 1000 | 7.4 | 7 | 12 | 28 | 2.9 |
| /api/v1/health | — | 1.9 | 1 | 3 | 10 | 3.2 |

Environment: macOS (Apple Silicon), Python 3.13, PostgreSQL 16 (Docker), 10 concurrent users, 60s run.
Tool: Locust 2.43.3. Total requests: 1863, failures: 0.

```bash
# Start API server
SECRET_KEY=test-key TESTING=1 uv run uvicorn api.main:app --port 8000

# Run benchmark (separate terminal)
uv run locust -f tests/performance/locustfile.py \
    --host http://localhost:8000 --headless \
    --users 10 --spawn-rate 2 --run-time 60s --csv results
```

## Production Performance

Run date: 2026-02-22 | Environment: Railway (Hobby), europe-west4, Cloudflare proxy

| Endpoint | Avg TTFB (ms) | Min (ms) | Max (ms) |
|----------|---------------|----------|----------|
| /api/v1/health | 417 | 222 | 534 |
| /api/v1/calculate (10 experts) | 437 | 210 | 504 |

Measured from Prague (CZ) via Cloudflare edge (PRG) → Railway (europe-west4, NL). TTFB includes network latency (~20ms round-trip), Cloudflare proxy overhead, and TLS negotiation. Actual compute time remains ~2-3ms per request; the difference from local benchmarks is purely network overhead.

## Configuration

mypy runs in strict mode (`pyproject.toml`). ruff enforces pycodestyle, pyflakes, isort, bugbear, and naming conventions. Line length is 100 characters.
