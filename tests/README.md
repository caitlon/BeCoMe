# BeCoMe Test Suite

This directory contains comprehensive tests for the BeCoMe (Best Compromise Mean) implementation, organized by test type and purpose. The test suite is part of a bachelor thesis at the Faculty of Economics and Management, Czech University of Life Sciences Prague.

## Overview

The test suite validates the correctness of the BeCoMe method implementation through:

- **Unit tests** - Isolated tests for individual components (models, calculators, interpreters, utilities)
- **Integration tests** - End-to-end validation against Excel reference implementation
- **Coverage analysis** - Comprehensive code coverage metrics ensuring all paths are tested

All tests follow the GIVEN-WHEN-THEN pattern for clarity and maintainability.

## Running Tests

### Prerequisites

Ensure dependencies are installed and virtual environment is activated:

```bash
uv sync
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate     # On Windows
```

### Basic Test Execution

Run all tests:

```bash
uv run pytest
```

Run tests from a specific file:

```bash
uv run pytest tests/unit/models/test_fuzzy_number.py
uv run pytest tests/unit/calculators/test_arithmetic_mean.py
uv run pytest tests/integration/test_excel_reference.py
```

Run all tests from a specific category:

```bash
uv run pytest tests/unit/             # All unit tests
uv run pytest tests/unit/models/      # Only model tests
uv run pytest tests/unit/calculators/ # Only calculator tests
uv run pytest tests/integration/      # Only integration tests
```

Run a specific test class or function:

```bash
uv run pytest tests/unit/models/test_fuzzy_number.py::TestFuzzyTriangleNumberCreation
uv run pytest tests/unit/models/test_expert_opinion.py::TestExpertOpinionComparison::test_less_than_comparison
```

### Test Output Options

Verbose output with detailed test names:

```bash
uv run pytest -v
```

Stop on first failure:

```bash
uv run pytest -x
```

Show print statements during tests:

```bash
uv run pytest -s
```

## Code Coverage

### Running Coverage Analysis

Basic coverage report:

```bash
uv run pytest --cov=src
```

Coverage with missing lines highlighted:

```bash
uv run pytest --cov=src --cov-report=term-missing
```

Coverage with branch analysis:

```bash
uv run pytest --cov=src --cov-report=term-missing --cov-branch
```

Generate HTML coverage report:

```bash
uv run pytest --cov=src --cov-report=html
```

HTML report will be generated in `htmlcov/` directory.

### Coverage Metrics

The BeCoMe implementation maintains **100% code coverage** across all source modules:

- All statements executed by tests
- All branches covered (including edge cases)
- All functions and methods tested
- Complete validation against Excel reference implementation

Test suite includes **202 tests** across all categories.

## Test Structure

Tests are organized by type for clarity and maintainability:

### Unit Tests (`tests/unit/`)

Fast, isolated tests for individual components.

#### Models (`tests/unit/models/`)

Unit tests for data models:

- [test_fuzzy_number.py](unit/models/test_fuzzy_number.py) - Tests for `FuzzyTriangleNumber` value object (27 tests)
  - Creation and validation
  - Centroid calculation
  - Comparison operations
  - Edge cases (crisp numbers, zero bounds)

- [test_expert_opinion.py](unit/models/test_expert_opinion.py) - Tests for `ExpertOpinion` dataclass (19 tests)
  - Opinion creation and validation
  - Centroid-based comparison
  - Sorting operations

- [test_become_result.py](unit/models/test_become_result.py) - Tests for `BeCoMeResult` Pydantic model (18 tests)
  - Result creation and validation
  - Field constraints and types
  - JSON serialization

#### Calculators (`tests/unit/calculators/`)

Unit tests for calculation logic:

- [test_arithmetic_mean.py](unit/calculators/test_arithmetic_mean.py) - Arithmetic mean calculation (5 tests)
  - Component-wise averaging
  - Multiple experts handling
  - Single expert edge case

- [test_median.py](unit/calculators/test_median.py) - Median calculation (9 tests)
  - Odd number of experts
  - Even number of experts
  - Centroid-based sorting

- [test_median_strategies.py](unit/calculators/test_median_strategies.py) - Median strategy pattern (7 tests)
  - Strategy selection (odd vs even)
  - Strategy correctness validation

- [test_compromise.py](unit/calculators/test_compromise.py) - Full BeCoMe calculation (6 tests)
  - Best compromise calculation
  - Maximum error estimation
  - Complete result validation

- [test_base_calculator.py](unit/calculators/test_base_calculator.py) - Abstract base calculator (7 tests)
  - Template method pattern validation
  - Centroid calculation utilities

#### Interpreters (`tests/unit/interpreters/`)

Unit tests for interpretation logic:

- [test_likert_interpreter.py](unit/interpreters/test_likert_interpreter.py) - Likert scale decision interpreter (15 tests)
  - Scale interpretation (0-100 to decision categories)
  - Boundary conditions
  - Edge case handling

#### Utilities (`tests/unit/utilities/`)

Unit tests for helper utilities (examples module):

- [test_utils_analysis.py](unit/utilities/test_utils_analysis.py) - Agreement level calculation (3 tests)
  - Expert agreement metrics
  - Quality assessment

- [test_utils_display.py](unit/utilities/test_utils_display.py) - Step-by-step display functions (8 tests)
  - Calculation step formatting
  - Formula display

- [test_utils_formatting.py](unit/utilities/test_utils_formatting.py) - Console formatting utilities (11 tests)
  - Header formatting
  - Section separators
  - Table formatting

### Integration Tests (`tests/integration/`)

End-to-end tests validating the full pipeline against Excel reference implementation:

- [test_excel_reference.py](integration/test_excel_reference.py) - Excel validation (9 tests)
  - Budget case validation (22 experts, even)
  - Floods case validation (13 experts, odd)
  - Pendlers case validation (22 experts, Likert scale)
  - Numerical precision validation (tolerance: 0.001)

- [test_data_loading.py](integration/test_data_loading.py) - Data loading pipeline (13 tests)
  - Text file parsing
  - Metadata extraction
  - Expert opinion construction
  - Error handling

### Reference Data (`tests/reference/`)

Test case data from Excel reference implementation:

- [budget_case.py](reference/budget_case.py) - Budget allocation case (22 experts, even)
- [floods_case.py](reference/floods_case.py) - Flood prevention case (13 experts, odd)
- [pendlers_case.py](reference/pendlers_case.py) - Cross-border travel case (22 experts, Likert scale)
- [_case_factory.py](reference/_case_factory.py) - Factory for creating test case dictionaries

Each reference case includes:
- Expert opinions as `ExpertOpinion` objects
- Expected results for validation
- Metadata about the case study

### Performance Tests (`tests/performance/`)

Placeholder directory for future performance benchmarks and scalability tests.

## Test Design Principles

### GIVEN-WHEN-THEN Pattern

All tests follow the GIVEN-WHEN-THEN structure:

```python
def test_example():
    # GIVEN: Setup test conditions
    opinions = [ExpertOpinion("E1", FuzzyTriangleNumber(5, 10, 15))]

    # WHEN: Execute the operation
    result = calculator.calculate_compromise(opinions)

    # THEN: Verify the outcome
    assert result.best_compromise.peak == expected_value
```

### Validation Strategy

Tests validate implementation correctness through:

1. **Excel reference comparison** - All calculations verified against Excel implementation to numerical precision (tolerance: 0.001)
2. **Edge case coverage** - Single expert, identical opinions, extreme values, boundary conditions
3. **Property-based testing** - Fuzzy number invariants and mathematical properties
4. **Type safety** - All type annotations validated through mypy in strict mode

### Test Independence

Each test is independent and can run in isolation:
- No shared state between tests
- Fresh fixtures for each test
- Deterministic outcomes

## Quality Metrics

The test suite ensures implementation quality through:

- **Code coverage**: 100% statement and branch coverage
- **Test count**: 202 comprehensive tests
- **Validation**: All calculations verified against Excel reference implementation
- **Type safety**: 100% mypy compliance in strict mode
- **Documentation**: Complete docstrings for all test cases

## Continuous Integration

Tests are designed to run in CI/CD pipelines:

```bash
# Full quality check
uv run mypy src/ examples/ && uv run ruff check . && uv run pytest --cov=src
```

## References

For implementation details and theoretical foundation:

- **Main documentation**: [../README.md](../README.md) - Project overview and installation
- **Documentation index**: [../docs/README.md](../docs/README.md) - Complete documentation navigation
- **Method description**: [../docs/method-description.md](../docs/method-description.md) - Mathematical foundation
- **API reference**: [../docs/api-reference.md](../docs/api-reference.md) - Complete API documentation
- **References**: [../docs/references.md](../docs/references.md) - Bibliography and cited sources
- **Source code**: [../src/README.md](../src/README.md) - Implementation architecture
- **Examples**: [../examples/README.md](../examples/README.md) - Case studies and usage examples

## Notes

All tests are part of the validation process for the bachelor thesis "BeCoMe Method Implementation" at the Faculty of Economics and Management, Czech University of Life Sciences Prague. The test suite demonstrates the correctness and reliability of the Python implementation compared to the original Excel reference calculations.
