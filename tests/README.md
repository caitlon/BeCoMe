# BeCoMe test suite

Tests for the BeCoMe implementation: 1,727 backend tests, plus 59 end-to-end tests that skip
unless a server and PostgreSQL are up. Coverage is 100% on the core library and 99% overall.

## Overview

Unit tests cover models, calculators, interpreters, utilities, and API components in isolation. Integration tests validate core results against the original Excel implementation (tolerance: 0.001) and test API routes with a real database. End-to-end tests exercise full API workflows. All tests follow the GIVEN-WHEN-THEN pattern.

## Running tests

```bash
uv run pytest                          # all tests
uv run pytest tests/unit/              # unit tests only
uv run pytest tests/integration/       # integration tests only
uv run pytest -v                       # verbose output
uv run pytest -x                       # stop on first failure
uv run pytest -n 0                     # serial, for a readable traceback
```

The suite runs in parallel by default: `-n auto` sits in `addopts`, one worker per
core. A full run that took 3:46 serially lands between one and two minutes. The
spread between repeats is wide enough that a single timing settles nothing, so
treat any number here as a range rather than a figure to tune against.

Use `-n 0` in two cases. The first is reading one failure closely, because worker
output interleaves. The second is any small selection: a single file costs more to
distribute than to run, 5.5 seconds against 3.0 for
`tests/unit/models/test_fuzzy_number.py`.

The end-to-end tests opt out explicitly, in `.github/workflows/ci.yml` and in
`scripts/ci/e2e-local.sh`. They share one uvicorn process and one database, so
workers queue behind each other until the client's ten-second timeout in
`tests/e2e/conftest.py` starts firing. At twelve workers a quarter of them failed
that way. At four they all passed. Anything new that drives the live stack needs
the same `-n 0`.

## Code coverage

```bash
uv run pytest --cov=src --cov-report=term-missing
uv run pytest --cov=src --cov-report=html          # generates htmlcov/
```

Current coverage: 100% on `src/`, and 99% across `src/` and `api/` together. About half the gap is
the Redis-backed store variants, which need a live Redis; the rest is scattered error
branches. CI measures the same number over
`tests/unit/` and `tests/integration/` only, because the end-to-end tests drive a separate
uvicorn process that in-process coverage cannot see.

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

- [Main README](../README.md): project overview
- [src/README.md](../src/README.md): implementation details
- [Method description](../docs/method-description.md): mathematical foundation
