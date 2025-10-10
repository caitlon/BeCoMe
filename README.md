# BeCoMe Method Implementation

Python implementation of the BeCoMe (Best Compromise Mean) method for group decision-making support under fuzzy uncertainty.

## Project Status

✅ **Production Ready** - Complete implementation with 100% test coverage

| Metric | Status |
|--------|--------|
| **Type Safety** | ✅ 100% (mypy strict mode) |
| **Code Style** | ✅ 100% (ruff) |
| **Test Coverage** | ✅ 100% (77/77 tests) |
| **Documentation** | ✅ Complete |

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

## Quick Start

### Running Examples

The easiest way to understand BeCoMe is to run one of the real-world case studies:

```bash
# COVID-19 budget support case (22 experts, even number)
python -m examples.analyze_budget_case

# Flood prevention case (13 experts, odd number)
python -m examples.analyze_floods_case

# Cross-border travel policy case (22 experts, Likert scale)
python -m examples.analyze_pendlers_case
```

Each example provides step-by-step calculations with detailed explanations.

### Basic Usage

```python
from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

# Create expert opinions
experts = [
    ExpertOpinion("Expert 1", FuzzyTriangleNumber(5.0, 10.0, 15.0)),
    ExpertOpinion("Expert 2", FuzzyTriangleNumber(8.0, 12.0, 18.0)),
    ExpertOpinion("Expert 3", FuzzyTriangleNumber(6.0, 11.0, 16.0)),
]

# Calculate best compromise
calculator = BeCoMeCalculator()
result = calculator.calculate_compromise(experts)

print(f"Best Compromise: {result.best_compromise}")
print(f"Max Error: {result.max_error}")
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
├── tests/                   # Test suite (100% coverage)
│   ├── models/             # Model tests
│   ├── calculators/        # Calculator tests
│   ├── integration/        # Integration tests with Excel
│   ├── examples/           # Tests for examples data loading
│   └── reference/          # Reference test data
├── examples/               # Practical examples
│   ├── data/              # Case study data in text format
│   ├── analyze_budget_case.py    # Budget support analysis
│   ├── analyze_floods_case.py    # Flood prevention analysis
│   └── analyze_pendlers_case.py  # Cross-border travel analysis
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

Current test coverage: **100%** (77 tests passing)

## Examples

The `examples/` directory contains three real-world case studies with detailed step-by-step analysis:

### 1. Budget Case (22 experts, even)
**Scenario**: COVID-19 pandemic budget support estimation (0-100 billion CZK)  
**Data**: Interval estimates from government officials and emergency service leaders  
**Key feature**: Demonstrates median calculation with even number of experts

### 2. Floods Case (13 experts, odd)
**Scenario**: Flood prevention - recommended percentage of arable land reduction  
**Data**: Highly polarized opinions (land owners vs. hydrologists/rescue services)  
**Key feature**: Demonstrates median calculation with odd number of experts and high disagreement

### 3. Pendlers Case (22 experts, even)
**Scenario**: Cross-border travel policy during pandemic  
**Data**: Likert scale ratings (0-25-50-75-100)  
**Key feature**: Demonstrates handling of crisp values as special case of fuzzy numbers

Each example:
- Loads data from simple text files (`examples/data/*.txt`)
- Shows all calculation steps with formulas
- Displays intermediate results (arithmetic mean, median, sorting)
- Provides interpretation of final results

See `examples/README.md` for detailed documentation.

## Documentation

Comprehensive documentation is available in the `docs/` directory:

| Document | Description |
|----------|-------------|
| **[Method Description](docs/method-description.md)** | Mathematical foundation with formulas and worked examples |
| **[API Reference](docs/api-reference.md)** | Complete API documentation for all classes and methods |
| **[UML Diagrams](docs/uml-diagrams.md)** | Visual architecture (class, sequence, activity diagrams) |
| **[Architecture](docs/architecture.md)** | Design decisions, patterns, and trade-offs |
| **[Quality Report](docs/quality-report.md)** | Code quality metrics and test coverage details |

### Quick Links

- 📖 **Learn the math**: Start with [Method Description](docs/method-description.md)
- 🔧 **Use the API**: Check [API Reference](docs/api-reference.md)
- 🎨 **See the architecture**: View [UML Diagrams](docs/uml-diagrams.md)
- 📊 **Verify quality**: Read [Quality Report](docs/quality-report.md)

git ## Code Quality

This project maintains high code quality standards:

```bash
# Type checking (strict mode)
mypy src/ examples/

# Linting
ruff check .

# Code formatting
ruff format .

# All quality checks
mypy src/ && ruff check . && pytest --cov=src
```

**Quality Metrics:**
- ✅ **100% type coverage** - All code strictly typed
- ✅ **100% test coverage** - 77 tests, all passing
- ✅ **100% linting** - No style violations
- ✅ **0.14s test execution** - Fast and reliable

See [Quality Report](docs/quality-report.md) for detailed metrics.

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux

# Run full quality check suite
mypy src/ examples/
ruff check .
ruff format .
pytest --cov=src --cov-report=term-missing
```

## License

This implementation is part of a bachelor thesis project at Czech University of Life Sciences Prague.

