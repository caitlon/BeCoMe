# BeCoMe Method Implementation

Python implementation of the BeCoMe (Best Compromise Mean) method for group decision-making under fuzzy uncertainty.

![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![License](https://img.shields.io/badge/license-Academic-blue)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)

## Project Information

- **Author**: Ekaterina Kuzmina
- **University**: Czech University of Life Sciences Prague
- **Faculty**: Faculty of Economics and Management (Provozně ekonomická fakulta)
- **Thesis Type**: Bachelor Thesis
- **Supervisor**: doc. Ing. Jan Tyrychtr, Ph.D.
- **Academic Year**: 2025/2026
- **Language**: English
- **Thesis Text**: Will be published upon completion

## Abstract

Group decision-making under uncertainty is a critical challenge in many domains, including public policy, emergency management, and resource allocation. Traditional aggregation methods often fail to capture the inherent fuzziness and disagreement among expert opinions, particularly when dealing with interval estimates or subjective assessments.

This thesis presents a Python implementation of the BeCoMe (Best Compromise Mean) method, which addresses these limitations by combining arithmetic mean and statistical median approaches within a fuzzy triangular number framework. The method provides a robust mechanism for aggregating expert opinions expressed as fuzzy triangular numbers, producing a consensus estimate that balances central tendency with distributional robustness.

The implementation is validated against three real-world case studies from public policy domain: COVID-19 budget allocation (22 experts), flood prevention planning (13 experts with polarized views), and cross-border travel policy assessment (22 experts using Likert scale). Complete test coverage and comprehensive documentation ensure reproducibility and facilitate future research applications.

## Motivation

Expert-based decision-making faces several challenges:

1. **Uncertainty representation**: Experts often express opinions as ranges or intervals rather than point estimates, reflecting inherent uncertainty in their assessments.

2. **Opinion aggregation**: Combining multiple expert opinions requires methods that preserve information about uncertainty while producing actionable consensus estimates.

3. **Robustness to outliers**: Traditional mean-based aggregation is sensitive to extreme opinions, while median-based approaches may lose information about the overall distribution.

4. **Practical applicability**: Decision support tools must be accessible to practitioners without requiring deep mathematical expertise.

The BeCoMe method addresses these challenges by combining the strengths of arithmetic mean (preserving distributional information) and statistical median (providing robustness), while working within a fuzzy triangular number framework that naturally represents expert uncertainty.

This implementation makes the method accessible through a well-documented Python library with practical examples from public policy applications.

## Methodology

### Method Overview

The BeCoMe method operates on expert opinions expressed as fuzzy triangular numbers **A** = (a, c, b), where:
- **a** = lower bound (pessimistic estimate)
- **c** = peak (most likely value)
- **b** = upper bound (optimistic estimate)

The algorithm proceeds through four steps:

1. **Arithmetic Mean (Γ)**: Calculate component-wise average of all expert opinions
2. **Median (Ω)**: Sort opinions by centroid values and compute median fuzzy number
3. **Best Compromise (ΓΩMean)**: Average the arithmetic mean and median
4. **Error Estimation (Δmax)**: Calculate maximum deviation as quality metric

### Implementation Approach

**Programming Language**: Python 3.13+

**Key Design Decisions**:
- Object-oriented architecture with clear separation between data models and calculation logic
- Strategy pattern for median calculation (odd vs. even number of experts)
- Immutable value objects for fuzzy numbers using `dataclasses`
- Type safety enforced through `mypy` in strict mode
- Comprehensive unit and integration testing with 100% code coverage

**Dependencies**:
- Core: Python standard library only (no external dependencies for calculation logic)
- Development: `pytest` for testing, `mypy` for type checking, `ruff` for linting
- Visualization: `matplotlib`, `seaborn`, `jupyter` (optional, for examples)

**Validation**:
- Implementation validated against Excel reference calculations from original research
- Three case studies with known expected results
- Numerical precision verified to 0.001 tolerance for all test cases

See [Architecture Documentation](docs/architecture.md) for detailed design rationale.

## Data

### Case Study Datasets

The implementation includes three real-world datasets from Czech public policy domain:

#### 1. Budget Case (budget_case.txt)
- **Domain**: COVID-19 pandemic budget support
- **Experts**: 22 (government officials, emergency service leaders)
- **Data Type**: Interval estimates (0-100 billion CZK)
- **Format**: Fuzzy triangular numbers
- **Characteristics**: Even number of experts, moderate agreement

#### 2. Floods Case (floods_case.txt)
- **Domain**: Flood prevention - arable land reduction
- **Experts**: 13 (land owners, hydrologists, rescue services)
- **Data Type**: Percentage estimates (0-100%)
- **Format**: Fuzzy triangular numbers
- **Characteristics**: Odd number of experts, highly polarized opinions

#### 3. Pendlers Case (pendlers_case.txt)
- **Domain**: Cross-border travel policy during pandemic
- **Experts**: 22 (public health officials, border services)
- **Data Type**: Likert scale ratings (0, 25, 50, 75, 100)
- **Format**: Crisp values (special case of fuzzy numbers where a = c = b)
- **Characteristics**: Even number of experts, ordinal scale data

### Data Format

All datasets are stored in human-readable text format in `examples/data/`:

```
CASE: CaseName
DESCRIPTION: Case description
EXPERTS: N

# Format: ExpertID | Lower | Peak | Upper
Expert1 | 10.0 | 15.0 | 20.0
Expert2 | 12.0 | 18.0 | 25.0
...
```

### Data Availability

- **Location**: `examples/data/` directory in this repository
- **License**: Academic use only (part of bachelor thesis)
- **Access**: Public (GitHub repository)

## Installation

### Requirements

- Python 3.13 or higher
- `uv` package manager (recommended) or `pip`

### Installation Steps

This project uses `uv` for dependency management:

```bash
# Clone the repository
git clone <repository-url>
cd BeCoMe

# Install dependencies using uv
uv sync

# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate     # On Windows
```

Alternatively, with pip:

```bash
pip install -e ".[dev]"
```

## Usage

### Running Case Study Examples

The easiest way to understand the BeCoMe method is to run one of the case study analyses:

```bash
# COVID-19 budget support case (22 experts, even number)
uv run python -m examples.analyze_budget_case

# Flood prevention case (13 experts, odd number)
uv run python -m examples.analyze_floods_case

# Cross-border travel policy case (22 experts, Likert scale)
uv run python -m examples.analyze_pendlers_case
```

Each example provides step-by-step calculations with detailed explanations of the mathematical operations.

### Basic API Usage

```python
from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

# Create expert opinions as fuzzy triangular numbers
experts = [
    ExpertOpinion("Expert 1", FuzzyTriangleNumber(5.0, 10.0, 15.0)),
    ExpertOpinion("Expert 2", FuzzyTriangleNumber(8.0, 12.0, 18.0)),
    ExpertOpinion("Expert 3", FuzzyTriangleNumber(6.0, 11.0, 16.0)),
]

# Calculate best compromise
calculator = BeCoMeCalculator()
result = calculator.calculate_compromise(experts)

# Access results
print(f"Best Compromise: {result.best_compromise}")
print(f"Arithmetic Mean: {result.arithmetic_mean}")
print(f"Median: {result.median}")
print(f"Max Error: {result.max_error}")
print(f"Number of Experts: {result.num_experts}")
```

See [API Reference](docs/api-reference.md) for complete documentation of all classes and methods.

## Project Structure

```
BeCoMe/
├── src/                    # Source code
│   ├── models/             # Data models
│   │   ├── fuzzy_number.py      # Fuzzy triangular number
│   │   ├── expert_opinion.py    # Expert opinion representation
│   │   └── become_result.py     # Result model
│   ├── calculators/        # Calculation logic
│   │   ├── become_calculator.py      # Main BeCoMe calculator
│   │   ├── base_calculator.py        # Abstract base calculator
│   │   └── median_strategies.py     # Median calculation strategies
│   ├── interpreters/       # Result interpretation
│   │   └── likert_interpreter.py    # Likert scale decision interpreter
│   └── exceptions.py       # Custom exceptions
├── tests/                  # Test suite
│   ├── unit/              # Unit tests
│   │   ├── models/             # Model tests
│   │   ├── calculators/        # Calculator tests
│   │   ├── interpreters/       # Interpreter tests
│   │   └── utilities/          # Utility function tests
│   ├── integration/       # Integration tests
│   │   ├── test_excel_reference.py    # Excel validation tests
│   │   └── test_data_loading.py       # Data loading tests
│   └── reference/         # Reference test data
│       ├── budget_case.py        # Budget case expected results
│       ├── floods_case.py        # Floods case expected results
│       └── pendlers_case.py      # Pendlers case expected results
├── examples/              # Practical examples
│   ├── data/             # Case study data files
│   │   ├── budget_case.txt
│   │   ├── floods_case.txt
│   │   └── pendlers_case.txt
│   ├── utils/            # Example utilities
│   │   ├── data_loading.py     # Data file parser
│   │   ├── display.py          # Step-by-step display
│   │   ├── formatting.py       # Output formatting
│   │   └── analysis.py         # Agreement analysis
│   ├── analyze_budget_case.py    # Budget case analysis
│   ├── analyze_floods_case.py    # Floods case analysis
│   └── analyze_pendlers_case.py  # Pendlers case analysis
├── docs/                  # Documentation
│   ├── method-description.md    # Mathematical foundation
│   ├── api-reference.md         # Complete API documentation
│   ├── architecture.md          # Design decisions
│   ├── uml-diagrams.md          # Visual architecture
│   └── quality-report.md        # Quality metrics
├── supplementary/         # Reference materials
│   └── [To be added: Excel implementation and research materials]
└── README.md             # This file
```

## Testing

The implementation includes comprehensive test coverage:

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=src --cov-report=term-missing

# Run specific test categories
uv run pytest tests/unit/              # Unit tests only
uv run pytest tests/integration/       # Integration tests only
uv run pytest tests/unit/models/       # Model tests only
```

### Test Coverage

Current test coverage: **100%** (all source code lines covered)

Test suite includes:
- 173 unit tests covering all models, calculators, and interpreters
- 29 integration tests validating against Excel reference implementation
- Property-based tests for fuzzy number operations
- Edge case coverage (single expert, identical opinions, extreme values)

See [Quality Report](docs/quality-report.md) for detailed test coverage metrics.

## Code Quality

The project maintains strict code quality standards:

```bash
# Type checking with mypy (strict mode)
uv run mypy src/ examples/

# Linting with ruff
uv run ruff check .

# Code formatting
uv run ruff format .

# Run all quality checks
uv run mypy src/ examples/ && uv run ruff check . && uv run pytest --cov=src
```

Quality metrics:
- Type safety: 100% (mypy strict mode, no type: ignore comments)
- Code style: 100% (ruff compliance)
- Test coverage: 100%
- Documentation: Complete docstrings for all public APIs

## Documentation

Comprehensive documentation is available in the `docs/` directory:

| Document | Description |
|----------|-------------|
| [Method Description](docs/method-description.md) | Mathematical foundation with formulas and worked examples |
| [API Reference](docs/api-reference.md) | Complete API documentation for all classes and methods |
| [UML Diagrams](docs/uml-diagrams.md) | Visual architecture (class, sequence, activity diagrams) |
| [Architecture](docs/architecture.md) | Design decisions, patterns, and trade-offs |
| [Quality Report](docs/quality-report.md) | Code quality metrics and test coverage details |

**Recommended reading order**:
1. [Method Description](docs/method-description.md) - Understand the mathematical foundation
2. [Architecture](docs/architecture.md) - Learn the design decisions
3. [API Reference](docs/api-reference.md) - Explore the implementation
4. [UML Diagrams](docs/uml-diagrams.md) - Visualize the structure

## Architecture

The implementation follows object-oriented design principles with clear separation of concerns:

### Class Diagram

![Class Diagram](docs/uml-diagrams/class-diagram.png)

*Complete architecture with sequence and activity diagrams available in [UML Documentation](docs/uml-diagrams.md)*

### Key Design Patterns

- **Value Object**: `FuzzyTriangleNumber` is immutable and validated on construction
- **Strategy Pattern**: Different median calculation strategies for odd/even expert counts
- **Template Method**: `BaseAggregationCalculator` defines calculation skeleton
- **Data Transfer Object**: `BeCoMeResult` encapsulates all calculation outputs

See [Architecture Documentation](docs/architecture.md) for detailed design rationale.

## Examples

The `examples/` directory contains three real-world case studies demonstrating the method:

### Budget Case (22 experts, even)
**Scenario**: COVID-19 pandemic budget support estimation (0-100 billion CZK)
**Participants**: Government officials and emergency service leaders
**Key Feature**: Demonstrates median calculation with even number of experts

### Floods Case (13 experts, odd)
**Scenario**: Flood prevention - recommended percentage of arable land reduction
**Participants**: Land owners, hydrologists, rescue service coordinators
**Key Feature**: Demonstrates median calculation with odd number of experts and highly polarized opinions

### Pendlers Case (22 experts, even)
**Scenario**: Cross-border travel policy during pandemic
**Participants**: Public health officials and border service representatives
**Key Feature**: Demonstrates handling of Likert scale data (crisp values as special case of fuzzy numbers)

Each example:
- Loads data from text files in `examples/data/`
- Shows all calculation steps with mathematical formulas
- Displays intermediate results (arithmetic mean, median, sorting process)
- Provides interpretation of final consensus estimate

See [examples/README.md](examples/README.md) for detailed documentation of example structure and usage.

## License

This implementation is part of a bachelor thesis at the Faculty of Economics and Management, Czech University of Life Sciences Prague.

**Academic Use**: This code is provided for academic and research purposes. If you use this implementation in academic work, please cite the thesis (full citation will be added upon publication).

**Copyright**: © 2025-2026 Ekaterina Kuzmina

## Contact

For questions or collaboration inquiries:

- **Author**: Ekaterina Kuzmina
- **Email**: xkuze010@studenti.czu.cz
- **University**: Czech University of Life Sciences Prague

## References

### Thesis Publication

Full thesis text will be available after publication and defense.

### Related Research

- Original BeCoMe method description and mathematical foundation (to be added to `supplementary/` directory)
- Excel reference implementation used for validation (to be added to `supplementary/` directory)
- UML diagrams and architecture documentation in `docs/uml-diagrams.md`

### Datasets

All case study datasets are included in this repository under `examples/data/`:
- `budget_case.txt` - COVID-19 budget allocation scenario
- `floods_case.txt` - Flood prevention planning scenario
- `pendlers_case.txt` - Cross-border travel policy scenario

## Acknowledgments

This work was supervised by doc. Ing. Jan Tyrychtr, Ph.D., at the Faculty of Economics and Management, Czech University of Life Sciences Prague.
