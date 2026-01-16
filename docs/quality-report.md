# Code Quality Report

## Summary

| Check | Status | Result |
|-------|--------|--------|
| mypy (strict) | Pass | No errors in 12 files |
| ruff check | Pass | No issues |
| ruff format | Pass | All files formatted |
| pytest | Pass | 202 tests, 0.14s |
| coverage | Pass | 100% |

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
| models/fuzzy_number.py | 15 | 100% |
| models/expert_opinion.py | 12 | 100% |
| models/become_result.py | 10 | 100% |
| calculators/become_calculator.py | 68 | 100% |
| **Total** | **105** | **100%** |

HTML report: `uv run pytest --cov=src --cov-report=html` generates `htmlcov/index.html`.

## Test Breakdown

Unit tests cover models (fuzzy numbers, expert opinions, results) and calculators (mean, median, compromise). Integration tests validate against Excel reference data for all three case studies — budget, floods, pendlers. Edge cases include single expert, identical opinions, empty lists, and boundary values.

## Configuration

mypy runs in strict mode (`pyproject.toml`). ruff enforces pycodestyle, pyflakes, isort, bugbear, and naming conventions. Line length is 100 characters.
