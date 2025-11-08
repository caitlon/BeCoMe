# Tests

This directory contains comprehensive tests for the BeCoMe library, organized by test type.

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
pytest tests/unit/models/test_fuzzy_number.py
pytest tests/unit/calculators/test_arithmetic_mean.py
pytest tests/integration/test_excel_reference.py
```

Run all tests from a specific category:

```bash
pytest tests/unit/             # All unit tests
pytest tests/unit/models/      # Only model tests
pytest tests/unit/calculators/ # Only calculator tests
pytest tests/integration/      # Only integration tests
pytest tests/performance/      # Performance/benchmark tests (when available)
```

Run a specific test class or function:

```bash
pytest tests/unit/models/test_fuzzy_number.py::TestFuzzyTriangleNumberCreation
pytest tests/unit/models/test_expert_opinion.py::TestExpertOpinionComparison::test_less_than_comparison
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

As of the last check, the project has **100% code coverage**! 🎉

```
Name                                   Stmts   Miss Branch BrPart  Cover
------------------------------------------------------------------------
src/__init__.py                            1      0      0      0   100%
src/calculators/__init__.py                2      0      0      0   100%
src/calculators/become_calculator.py      54      0      8      0   100%
src/models/__init__.py                     4      0      0      0   100%
src/models/become_result.py               12      0      0      0   100%
src/models/expert_opinion.py              19      0      2      0   100%
src/models/fuzzy_number.py                13      0      2      0   100%
------------------------------------------------------------------------
TOTAL                                    105      0     12      0   100%
```

All **202 tests** passing ✅

## Test Structure

Tests are organized by test type for better clarity and maintainability:

### Unit Tests (`tests/unit/`)
Fast, isolated tests for individual components.

#### Models (`tests/unit/models/`)
Unit tests for data models:
- `test_fuzzy_number.py` - Tests for `FuzzyTriangleNumber` value object (27 tests)
- `test_expert_opinion.py` - Tests for `ExpertOpinion` dataclass (19 tests)
- `test_become_result.py` - Tests for `BeCoMeResult` Pydantic model (18 tests)

#### Calculators (`tests/unit/calculators/`)
Unit tests for calculation logic:
- `test_arithmetic_mean.py` - Tests for arithmetic mean calculation (5 tests)
- `test_median.py` - Tests for median calculation (9 tests)
- `test_median_strategies.py` - Tests for median strategy pattern (7 tests)
- `test_compromise.py` - Tests for full BeCoMe compromise calculation (6 tests)
- `test_base_calculator.py` - Tests for abstract base calculator (7 tests)

#### Interpreters (`tests/unit/interpreters/`)
Unit tests for interpretation logic:
- `test_likert_interpreter.py` - Tests for Likert scale decision interpreter (15 tests)

#### Utilities (`tests/unit/utilities/`)
Unit tests for helper utilities (examples module):
- `test_utils_analysis.py` - Tests for agreement level calculation (3 tests)
- `test_utils_display.py` - Tests for step-by-step display functions (8 tests)
- `test_utils_formatting.py` - Tests for console formatting utilities (11 tests)

### Integration Tests (`tests/integration/`)
End-to-end tests validating the full pipeline:
- `test_excel_reference.py` - Validation against Excel reference implementation (9 tests)
- `test_data_loading.py` - Data loading and parsing pipeline (13 tests)

### Performance Tests (`tests/performance/`)
Placeholder directory for future performance benchmarks.

### Reference Data (`tests/reference/`)
Test case data from Excel reference implementation:
- `budget_case.py` - Budget allocation case
- `pendlers_case.py` - Pendlers case (Likert scale)
- `floods_case.py` - Floods case (13 experts)
- `_case_factory.py` - Factory for creating test case dictionaries