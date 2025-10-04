# Tests

This directory contains unit tests for the BeCoMe library.

## Running Tests

Make sure you're in the project root and have activated the virtual environment:

```bash
source venv/bin/activate
```

### Basic test run

Run all tests:

```bash
pytest
```

Run tests from a specific file:

```bash
pytest tests/test_fuzzy_number.py
pytest tests/test_expert_opinion.py
```

Run a specific test class or function:

```bash
pytest tests/test_fuzzy_number.py::TestFuzzyTriangleNumberCreation
pytest tests/test_expert_opinion.py::TestExpertOpinionComparison::test_less_than_comparison
```

### Verbose output

For more detailed output:

```bash
pytest -v
```

### Stop on first failure

```bash
pytest -x
```

## Code Coverage

Check test coverage:

```bash
pytest --cov=src tests/
```

With branch coverage and missing lines:

```bash
pytest --cov=src --cov-report=term-missing --cov-branch tests/
```

## Current Coverage Status

As of the last check, the project has **100% code coverage** including branch coverage! 🎉

```
Name                           Stmts   Miss Branch BrPart  Cover
------------------------------------------------------------------
src/__init__.py                    1      0      0      0   100%
src/models/__init__.py             3      0      0      0   100%
src/models/expert_opinion.py      19      0      2      0   100%
src/models/fuzzy_number.py        13      0      2      0   100%
------------------------------------------------------------------
TOTAL                             36      0      4      0   100%
```

## Test Structure

Tests are organized by module:

- `test_fuzzy_number.py` - Tests for `FuzzyTriangleNumber` class
- `test_expert_opinion.py` - Tests for `ExpertOpinion` class