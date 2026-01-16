# BeCoMe Test Suite

Tests for the BeCoMe implementation: 202 tests total, 100% code coverage.

## Overview

Unit tests cover models, calculators, and interpreters in isolation. Integration tests validate results against the original Excel implementation (tolerance: 0.001). All tests follow the GIVEN-WHEN-THEN pattern.

## Running Tests

```bash
uv run pytest                          # all tests
uv run pytest tests/unit/              # unit tests only
uv run pytest tests/integration/       # integration tests only
uv run pytest -v                       # verbose output
uv run pytest -x                       # stop on first failure
```

## Code Coverage

```bash
uv run pytest --cov=src --cov-report=term-missing
uv run pytest --cov=src --cov-report=html          # generates htmlcov/
```

Current coverage: 100% (all statements and branches).

## Test Structure

```
tests/
├── unit/
│   ├── models/          # FuzzyTriangleNumber, ExpertOpinion, BeCoMeResult
│   ├── calculators/     # arithmetic mean, median, strategies, compromise
│   ├── interpreters/    # Likert scale interpreter
│   └── utilities/       # display, formatting, analysis helpers
├── integration/
│   ├── test_excel_reference.py   # validates against Excel (3 case studies)
│   └── test_data_loading.py      # text file parsing
└── reference/
    ├── budget_case.py    # 22 experts, expected results
    ├── floods_case.py    # 13 experts, expected results
    └── pendlers_case.py  # 22 experts, Likert scale
```

**Unit tests** check individual components in isolation. **Integration tests** run the full pipeline and compare against Excel results (tolerance: 0.001). **Reference data** contains expected values from the original Excel implementation.

## Writing Tests

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

Each test runs in isolation — no shared state, fresh fixtures, deterministic outcomes.

## Related Documentation

- [Main README](../README.md) — project overview
- [src/README.md](../src/README.md) — implementation details
- [Method description](../docs/method-description.md) — mathematical foundation
