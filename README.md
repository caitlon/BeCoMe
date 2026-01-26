# BeCoMe

Full-stack web application for group decision-making under fuzzy uncertainty using the BeCoMe (Best Compromise Mean) method.

**🌐 Live: [becomify.app](https://www.becomify.app)**

![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![TypeScript](https://img.shields.io/badge/typescript-5.0+-blue.svg)
![FastAPI](https://img.shields.io/badge/fastapi-0.115+-green.svg)
![React](https://img.shields.io/badge/react-19+-blue.svg)
![Tests](https://img.shields.io/badge/tests-810%20passed-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)

## Table of Contents

- [Project Information](#project-information)
- [Abstract](#abstract)
- [Features](#features)
- [Quick Start](#quick-start)
- [Web Application](#web-application)
- [Methodology](#methodology)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Documentation](#documentation)
- [License](#license)
- [References](#references)

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

## Features

### Web Application
- **REST API**: FastAPI backend with JWT authentication
- **React Frontend**: Modern UI with TypeScript and Tailwind CSS
- **Project Management**: Create projects, invite experts, collect opinions
- **Real-time Calculations**: Automatic BeCoMe aggregation when opinions are submitted
- **Multi-language**: English and Czech localization

### Core Library
- **Fuzzy Triangular Numbers**: Operations on TFN (a, c, b) with validation
- **BeCoMe Algorithm**: Arithmetic mean + median → best compromise
- **Strategy Pattern**: Handles odd/even expert counts for median calculation
- **Likert Scale Support**: Ordinal data as special case of fuzzy numbers

### Quality
- **100% Test Coverage**: 810+ tests for API, frontend, and core library
- **Type Safety**: mypy strict mode, TypeScript strict
- **Three Case Studies**: COVID-19 budget, flood prevention, cross-border travel

## Web Application

The project includes a full-stack web application for collaborative decision-making.

### Architecture

| Component | Technology | Port |
|-----------|------------|------|
| Backend | FastAPI + SQLModel | 8000 |
| Frontend | React + Vite + Tailwind | 5173 |
| Database | SQLite (dev) / PostgreSQL (prod) | — |

### Key Features

- **User Authentication**: JWT-based auth with refresh tokens
- **Project Management**: Create projects with custom scales, invite experts by email
- **Opinion Collection**: Experts submit fuzzy triangular numbers (lower, peak, upper)
- **Automatic Calculation**: BeCoMe result computed when opinions are submitted
- **Role-based Access**: Admin and member roles per project

### Live Application

**https://www.becomify.app**

### Local Development

```bash
# Backend (http://localhost:8000)
uv sync --extra api
uv run uvicorn api.main:app --reload

# Frontend (http://localhost:5173)
cd frontend && npm install && npm run dev
```

See [api/README.md](api/README.md) for API documentation.

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
- Core: `pydantic` for data validation (the only runtime dependency)
- Development: `pytest`, `mypy`, `ruff` (optional, via `--extra dev`)
- Visualization: `matplotlib`, `plotly`, `seaborn` (optional, via `--extra viz`)
- Notebooks: `jupyter`, `ipykernel` (optional, via `--extra notebook`)

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

### Web Application

**Live demo:** https://www.becomify.app

Register, create a project, invite experts, and collect opinions — no installation required.

### Command Line (Case Studies)

```bash
uv sync --extra dev
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

# Install core dependencies only
uv sync

# Install with development tools (testing, linting, type checking)
uv sync --extra dev

# Install with visualization libraries (matplotlib, plotly, seaborn)
uv sync --extra viz

# Install with Jupyter notebook support
uv sync --extra notebook

# Install everything
uv sync --all-extras

# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate     # On Windows
```

### Dependency Groups

| Group | Contents | Use Case |
|-------|----------|----------|
| (core) | pydantic | Minimal installation for using the library |
| `dev` | pytest, mypy, ruff, pytest-cov | Development and testing |
| `viz` | numpy, pandas, matplotlib, plotly, seaborn | Visualization and data analysis |
| `notebook` | jupyter, ipykernel, ipywidgets | Interactive notebooks |
| `docs` | plantuml | UML diagram generation |

Alternatively, with pip:

```bash
pip install -e ".[dev,viz,notebook]"
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

```text
BeCoMe/
├── api/                    # REST API (FastAPI)
│   ├── auth/                   # Authentication (JWT, passwords)
│   ├── db/                     # Database models (SQLModel)
│   ├── routes/                 # HTTP endpoints
│   ├── schemas/                # Pydantic DTOs
│   ├── services/               # Business logic
│   └── README.md               # API documentation
├── frontend/               # Web UI (React + Vite)
│   ├── src/
│   │   ├── components/         # UI components (shadcn/ui)
│   │   ├── pages/              # Route pages
│   │   ├── contexts/           # React contexts
│   │   └── i18n/               # Translations (en, cs)
│   └── README.md
├── src/                    # Core library
│   ├── models/                 # Fuzzy number, expert opinion
│   ├── calculators/            # BeCoMe algorithm
│   └── interpreters/           # Likert scale support
├── tests/                  # Test suite (810+ tests)
│   ├── api/                    # API tests
│   ├── unit/                   # Core library tests
│   └── integration/            # Excel validation tests
├── examples/               # Case study examples
│   └── data/                   # Dataset files
└── docs/                   # Documentation
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
