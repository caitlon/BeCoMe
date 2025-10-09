# BeCoMe Method Implementation

Python implementation of the BeCoMe (Best Compromise Mean) method for group decision-making support under fuzzy uncertainty.

## Project Status

This project is under active development.

## Overview

BeCoMe is a method for aggregating expert opinions expressed as fuzzy triangular numbers to find the optimal compromise solution. The method combines arithmetic mean and statistical median to produce a robust consensus estimate.

**Key features:**
- Arithmetic mean calculation (Gamma)
- Statistical median calculation (Omega)
- Best compromise calculation (GammaOmegaMean)
- Maximum error estimation
- Support for both odd and even number of experts

## Installation

This project uses `uv` for dependency management. Make sure you have Python 3.13+ installed.

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

## Project Structure

```
BeCoMe/
├── src/
│   ├── models/              # Data models
│   │   ├── fuzzy_number.py      # Fuzzy triangular number
│   │   ├── expert_opinion.py    # Expert opinion representation
│   │   └── become_result.py     # Result model
│   └── calculators/         # Calculation logic
│       └── become_calculator.py # Main BeCoMe calculator
├── tests/                   # Test suite (99% coverage)
│   ├── models/             # Model tests
│   ├── calculators/        # Calculator tests
│   ├── integration/        # Integration tests
│   └── reference/          # Reference test data
├── scripts/                # Utility scripts
├── docs/                   # Documentation
└── supplementary/          # Reference materials and Excel implementation
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=term-missing

# Run specific test categories
pytest tests/models/
pytest tests/calculators/
pytest tests/integration/
```

Current test coverage: **99%** (61 tests passing)

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run linter
ruff check .

# Run type checker
mypy src/

# Format code
ruff format .
```

## License

This implementation is part of a bachelor thesis project at Czech University of Life Sciences Prague.

