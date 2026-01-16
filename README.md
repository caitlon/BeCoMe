# BeCoMe Method Implementation

Python implementation of the BeCoMe (Best Compromise Mean) method for group decision-making under fuzzy uncertainty.

![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![License](https://img.shields.io/badge/license-Academic-blue)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)

## Table of Contents

- [Project Information](#project-information)
- [Abstract](#abstract)
- [Motivation](#motivation)
- [Features](#features)
- [Methodology](#methodology)
- [Data](#data)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Documentation](#documentation)
- [Architecture](#architecture)
- [Examples](#examples)
- [License](#license)
- [Contact](#contact)
- [References](#references)
- [Acknowledgments](#acknowledgments)

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

**BeCoMe** (Best Compromise Mean) is a group decision-making method that aggregates expert opinions expressed as fuzzy triangular numbers. This Python implementation combines arithmetic mean and median approaches to produce consensus estimates balancing central tendency with outlier resistance.

Validated on three Czech case studies (COVID-19 budget allocation, flood prevention, cross-border travel policy). Results verified against original Excel implementation with 100% test coverage.

## Motivation

Expert opinions are ranges, not points. Traditional aggregation methods either lose information about uncertainty or fail to handle outliers well. Most existing tools are difficult to use in practice.

BeCoMe addresses these problems. Arithmetic mean preserves distributional information; median provides robustness to outliers. Combining both in a fuzzy triangular number framework gives better consensus estimates. This library includes three worked examples from Czech policy decisions.

## Features

- **Fuzzy Triangular Number Operations**: Addition, averaging, and centroid calculation for TFN
- **Arithmetic Mean Aggregation**: Component-wise averaging of expert opinions
- **Median Aggregation**: Centroid-based sorting with odd/even handling via Strategy pattern
- **Best Compromise Calculation**: Combined mean-median approach for robust consensus
- **Error Estimation**: Maximum deviation metric for result quality assessment
- **Likert Scale Support**: Handle ordinal scale data as special case of fuzzy numbers
- **Three Real-World Case Studies**: COVID-19 budget, flood prevention, cross-border travel
- **100% Test Coverage**: Unit and integration tests for all modules
- **Type Safety**: Full mypy strict mode compliance
- **Excel Validation**: Results verified against original Excel implementation

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
- Object-oriented architecture separating data models from calculation logic
- Strategy pattern for median calculation (odd vs. even number of experts)
- Immutable value objects for fuzzy numbers using `dataclasses`
- Type safety enforced through `mypy` in strict mode
- Unit and integration testing with 100% code coverage

**Dependencies**:
- Core: Python standard library only (no external dependencies for calculation logic)
- Development: `pytest` for testing, `mypy` for type checking, `ruff` for linting
- Visualization: `matplotlib`, `seaborn`, `jupyter` (optional, for examples)

**Validation**: Results match Excel reference calculations from the original research. All three case studies produce expected values within 0.001 tolerance.

## Data

### Case Study Datasets

The implementation includes three real-world datasets from Czech public policy domain:

#### 1. Budget Case (budget_case.txt)

COVID-19 pandemic budget support estimation. 22 experts (government officials, emergency service leaders) provided interval estimates in billions of CZK. Demonstrates median calculation with an even number of experts.

#### 2. Floods Case (floods_case.txt)

Flood prevention planning — what percentage of arable land should be converted? 13 experts from different backgrounds (land owners, hydrologists, rescue services) show highly polarized opinions. This case demonstrates median calculation with an odd expert count.

#### 3. Pendlers Case (pendlers_case.txt)

Cross-border travel policy during pandemic. 22 public health officials and border service representatives rated policy options on a Likert scale (0, 25, 50, 75, 100). Uses crisp values — a special case where a = c = b in fuzzy number notation.

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

## Quick Start

Get results in under 3 minutes:

```bash
git clone <repository-url>
cd BeCoMe
uv sync
uv run python -m examples.analyze_budget_case
```

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

See [src/README.md](src/README.md) for API documentation.

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
│   │   ├── README.md            # Dataset documentation
│   │   ├── budget_case.txt      # COVID-19 budget case
│   │   ├── floods_case.txt      # Flood prevention case
│   │   └── pendlers_case.txt    # Cross-border travel case
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
│   ├── quality-report.md        # Quality metrics
│   └── uml-diagrams/            # UML diagrams (PNG, PUML, README)
├── supplementary/         # Reference materials
└── README.md             # This file
```

## Testing

The implementation includes full test coverage:

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

Current test coverage: **100%** (all source code lines covered).

The test suite contains 173 unit tests for models, calculators, and interpreters. Another 29 integration tests validate results against the original Excel implementation. Edge cases like single expert, identical opinions, and extreme values are covered. Property-based tests verify fuzzy number arithmetic.

See [Quality Report](docs/quality-report.md) for detailed metrics.

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

All code passes mypy in strict mode without `type: ignore` comments. Ruff enforces consistent style. Every public API has docstrings.

## Documentation

Documentation is available in the `docs/` directory:

| Document | Description |
|----------|-------------|
| [Method Description](docs/method-description.md) | Mathematical foundation with formulas and worked examples |
| [UML Diagrams](docs/uml-diagrams/README.md) | Visual architecture (class, sequence, activity diagrams) |
| [Quality Report](docs/quality-report.md) | Code quality metrics and test coverage details |
| [Source Code](src/README.md) | API documentation and module descriptions |

## Architecture

The implementation follows object-oriented design principles:

### Class Diagram

![Class Diagram](docs/uml-diagrams/diagrams/png/class-diagram.png)

*Complete architecture with sequence and activity diagrams available in [UML Documentation](docs/uml-diagrams/README.md)*

### Design Patterns

`FuzzyTriangleNumber` is a value object — immutable and validated on construction. The median calculation uses Strategy pattern to handle odd and even expert counts differently. `BaseAggregationCalculator` applies Template Method for the calculation skeleton, while `BeCoMeResult` serves as a DTO encapsulating all outputs.

## Examples

The `examples/` directory contains three real-world case studies demonstrating the method:

### Budget Case (22 experts)

Government officials and emergency service leaders estimated COVID-19 budget support needs (0-100 billion CZK). With an even number of experts, this case shows how the median is calculated by averaging two middle values.

### Floods Case (13 experts)

Land owners, hydrologists, and rescue coordinators disagreed strongly on flood prevention measures. The polarized opinions make this case interesting — it demonstrates how BeCoMe handles outliers when expert count is odd.

### Pendlers Case (22 experts)

Public health officials rated cross-border travel policies on a Likert scale. Unlike other cases, this one uses crisp values (where a = c = b), showing that fuzzy numbers generalize ordinal scales.

Running any example loads data from `examples/data/`, walks through the calculation step by step, and shows intermediate results (arithmetic mean, median, sorting process). The output includes interpretation of the final consensus estimate.

See [examples/README.md](examples/README.md) for details.

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

The BeCoMe method was developed by I. Vrana, J. Tyrychtr, and M. Pelikán at the Faculty of Economics and Management, Czech University of Life Sciences Prague.

**Key reference:**
- Vrana, I., Tyrychtr, J., & Pelikán, M. (2021). BeCoMe: Easy-to-implement optimized method for best-compromise group decision making: Flood-prevention and COVID-19 case studies. *Environmental Modelling & Software*, 136, 104953. https://doi.org/10.1016/j.envsoft.2020.104953

The thesis bibliography includes fuzzy logic foundations (Zadeh 1965, Bellman & Zadeh 1970), software engineering references, and all sources cited in the research.

### Datasets

All case study data is in `examples/data/`. The budget case has 22 experts estimating COVID-19 support. Floods case involves 13 experts with polarized views on land reduction. Pendlers case uses Likert scale ratings from 22 officials on cross-border travel policy.

See [examples/data/README.md](examples/data/README.md) for format specifications and data provenance.

## Acknowledgments

This work was supervised by doc. Ing. Jan Tyrychtr, Ph.D., at the Faculty of Economics and Management, Czech University of Life Sciences Prague.
