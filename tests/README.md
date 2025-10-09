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
pytest tests/models/test_fuzzy_number.py
pytest tests/calculators/test_become_calculator.py
pytest tests/integration/test_excel_reference.py
```

Run a specific test class or function:

```bash
pytest tests/models/test_fuzzy_number.py::TestFuzzyTriangleNumberCreation
pytest tests/models/test_expert_opinion.py::TestExpertOpinionComparison::test_less_than_comparison
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

As of the last check, the project has **99% code coverage**!

```
Name                                   Stmts   Miss  Cover
----------------------------------------------------------
src/__init__.py                            1      0   100%
src/calculators/__init__.py                2      0   100%
src/calculators/become_calculator.py      54      0   100%
src/models/__init__.py                     4      0   100%
src/models/become_result.py               12      1    92%
src/models/expert_opinion.py              19      0   100%
src/models/fuzzy_number.py                13      0   100%
----------------------------------------------------------
TOTAL                                    105      1    99%
```

All **61 tests** passing 

## Test Structure

Tests are organized into logical categories:

### Models (`tests/models/`)
Unit tests for data models:
- `test_fuzzy_number.py` - Tests for `FuzzyTriangleNumber` class 
- `test_expert_opinion.py` - Tests for `ExpertOpinion` class 

### Calculators (`tests/calculators/`)
Unit tests for calculation logic:
- `test_become_calculator.py` - Tests for `BeCoMeCalculator` class

### Integration (`tests/integration/`)
Integration tests with reference data:
- `test_excel_reference.py` - Tests against Excel reference implementation 

### Reference Data (`tests/reference/`)
Test case data from Excel reference:
- `budget_case.py` - Budget allocation case
- `pendlers_case.py` - Pendlers case (Likert scale)
- `floods_case.py` - Floods case (13 experts)