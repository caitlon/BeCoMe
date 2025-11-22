# BeCoMe Source Code

This directory contains the core implementation of the BeCoMe (Best Compromise Mean) method for aggregating expert opinions under fuzzy uncertainty. The implementation is part of a bachelor thesis at the Faculty of Economics and Management, Czech University of Life Sciences Prague.

## Overview

The source code is organized into three distinct layers following clean architecture principles:

- **Models** - Immutable data structures representing domain entities
- **Calculators** - Business logic for aggregating expert opinions
- **Interpreters** - Result interpretation for decision-making contexts

All code follows strict type safety (mypy strict mode), maintains 100% test coverage, and implements established design patterns for maintainability and extensibility.

## Architecture

### Layered Structure

```
src/
├── models/              # Domain models (Value Objects)
│   ├── fuzzy_number.py       # Fuzzy triangular number representation
│   ├── expert_opinion.py     # Expert opinion with identifier
│   └── become_result.py      # Calculation result (Pydantic model)
├── calculators/         # Calculation logic
│   ├── base_calculator.py        # Abstract base calculator (Template Method)
│   ├── median_strategies.py     # Median calculation strategies (Strategy Pattern)
│   └── become_calculator.py     # Main BeCoMe implementation
├── interpreters/        # Result interpretation
│   └── likert_interpreter.py    # Likert scale decision interpreter
├── exceptions.py        # Custom exception hierarchy
└── __init__.py         # Package marker with version
```

### Dependency Flow

```
interpreters/
    ↓
calculators/
    ↓
models/
    ↓
exceptions.py
```

Components depend only on lower layers, ensuring clean separation of concerns.

## Module Descriptions

### Models Layer (`models/`)

Immutable value objects representing domain entities in the BeCoMe method.

#### [fuzzy_number.py](models/fuzzy_number.py)

Implements `FuzzyTriangleNumber` as an immutable value object.

**Key features**:
- Represents fuzzy triangular numbers: (lower_bound, peak, upper_bound)
- Validates constraint: lower_bound ≤ peak ≤ upper_bound
- Calculates centroid: (lower + peak + upper) / 3
- Provides component-wise averaging for aggregation
- Immutable through `__slots__` and attribute protection

**Design patterns**: Value Object, Immutability

**Usage**:
```python
from src.models.fuzzy_number import FuzzyTriangleNumber

# Create fuzzy number
fuzzy = FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0)

# Access properties
print(fuzzy.centroid)  # 15.0

# Average multiple fuzzy numbers
avg = FuzzyTriangleNumber.average([fuzzy1, fuzzy2])
```

#### [expert_opinion.py](models/expert_opinion.py)

Implements `ExpertOpinion` combining expert identifier with fuzzy assessment.

**Key features**:
- Associates expert ID with fuzzy triangular number opinion
- Supports comparison operations based on centroid values
- Enables sorting of opinions for median calculation
- Immutable through `__slots__` and attribute protection

**Design patterns**: Value Object, Immutability, Comparable

**Usage**:
```python
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

opinion = ExpertOpinion(
    expert_id="Expert1",
    opinion=FuzzyTriangleNumber(10.0, 15.0, 20.0)
)

# Comparison based on centroid
opinions_sorted = sorted([opinion1, opinion2, opinion3])
```

#### [become_result.py](models/become_result.py)

Implements `BeCoMeResult` using Pydantic for validated, immutable results.

**Key features**:
- Stores best compromise (ΓΩMean), arithmetic mean (Γ), and median (Ω)
- Includes maximum error (Δmax) as quality metric
- Validates field constraints (num_experts ≥ 1, max_error ≥ 0)
- Computed property for even/odd expert count
- Factory method `from_calculations()` for automatic derivation

**Design patterns**: Data Transfer Object, Factory Method, Immutability

**Usage**:
```python
from src.models.become_result import BeCoMeResult

result = BeCoMeResult.from_calculations(
    arithmetic_mean=mean_fuzzy,
    median=median_fuzzy,
    num_experts=22
)

print(result.best_compromise)  # Automatically calculated
print(result.max_error)        # Automatically calculated
```

### Calculators Layer (`calculators/`)

Business logic for aggregating expert opinions using the BeCoMe method.

#### [base_calculator.py](calculators/base_calculator.py)

Abstract base class defining the calculator interface.

**Key features**:
- Defines contract for opinion aggregation
- Template Method pattern for calculation flow
- Type hints using `TYPE_CHECKING` for circular dependency avoidance

**Design patterns**: Abstract Base Class, Template Method

**Interface**:
- `calculate_arithmetic_mean()` - Component-wise averaging
- `calculate_median()` - Statistical median with sorting
- `calculate_compromise()` - Best compromise combining mean and median
- `sort_by_centroid()` - Opinion ordering for median calculation

#### [median_strategies.py](calculators/median_strategies.py)

Strategy pattern implementation for median calculation.

**Key features**:
- `MedianCalculationStrategy` (ABC) - Strategy interface
- `OddMedianStrategy` - Median for odd number of experts (M = 2n + 1)
- `EvenMedianStrategy` - Median for even number of experts (M = 2n)
- Finds opinions closest to median centroid value

**Design patterns**: Strategy Pattern

**Strategies**:

1. **OddMedianStrategy**: Returns middle element after sorting
2. **EvenMedianStrategy**: Averages two middle elements after sorting

**Usage**:
```python
from src.calculators.median_strategies import OddMedianStrategy, EvenMedianStrategy

# Strategy selection based on expert count
strategy = OddMedianStrategy() if m % 2 == 1 else EvenMedianStrategy()
median = strategy.calculate(sorted_opinions, median_centroid)
```

#### [become_calculator.py](calculators/become_calculator.py)

Main implementation of the BeCoMe method.

**Key features**:
- Implements `BaseAggregationCalculator` interface
- Calculates arithmetic mean (Γ): component-wise average
- Calculates median (Ω): statistical median with strategy selection
- Calculates best compromise (ΓΩMean): average of mean and median
- Computes maximum error (Δmax): quality indicator

**Formulas implemented**:

1. **Arithmetic Mean (Γ)**:
   - α = (1/M) × Σ(Aₖ) - average of lower bounds
   - γ = (1/M) × Σ(Cₖ) - average of peaks
   - β = (1/M) × Σ(Bₖ) - average of upper bounds

2. **Median (Ω)**:
   - Sort opinions by centroid
   - Odd: middle element
   - Even: average of two middle elements

3. **Best Compromise (ΓΩMean)**:
   - π = (α + ρ) / 2
   - φ = (γ + ω) / 2
   - ξ = (β + σ) / 2

4. **Maximum Error (Δmax)**:
   - Δmax = |centroid(Γ) - centroid(Ω)| / 2

**Usage**:
```python
from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

calculator = BeCoMeCalculator()

opinions = [
    ExpertOpinion("E1", FuzzyTriangleNumber(10, 15, 20)),
    ExpertOpinion("E2", FuzzyTriangleNumber(12, 18, 24)),
    ExpertOpinion("E3", FuzzyTriangleNumber(8, 13, 18))
]

result = calculator.calculate_compromise(opinions)
```

### Interpreters Layer (`interpreters/`)

Interpretation of calculation results for decision-making contexts.

#### [likert_interpreter.py](interpreters/likert_interpreter.py)

Interprets fuzzy numbers using Likert scale for policy decisions.

**Key features**:
- Maps fuzzy number centroids to Likert scale (0, 25, 50, 75, 100)
- Generates human-readable decision text
- Provides action recommendations for policy-making
- Returns immutable `LikertDecision` data class

**Likert scale mapping**:
- 0: Strongly disagree → Reject policy
- 25: Rather disagree → Significant revision needed
- 50: Neutral → Further analysis required
- 75: Rather agree → Recommend with minor adjustments
- 100: Strongly agree → Strongly recommend implementation

**Usage**:
```python
from src.interpreters.likert_interpreter import LikertDecisionInterpreter

interpreter = LikertDecisionInterpreter()
decision = interpreter.interpret(result.best_compromise)

print(decision.likert_value)      # 75
print(decision.decision_text)     # "Rather agree"
print(decision.recommendation)    # "Policy is recommended..."
```

### Exception Hierarchy (`exceptions.py`)

Custom exception classes for BeCoMe-specific errors.

**Exception hierarchy**:
```
BeCoMeError (base)
├── EmptyOpinionsError    # Empty opinions list provided
├── InvalidOpinionError   # Invalid opinion data
└── CalculationError      # Calculation failure
```

**Usage**:
```python
from src.exceptions import EmptyOpinionsError

try:
    result = calculator.calculate_compromise([])
except EmptyOpinionsError as e:
    print(f"Error: {e}")
```

## Design Patterns

The implementation applies several design patterns for maintainability and extensibility:

### 1. Value Object Pattern

**Applied in**: `FuzzyTriangleNumber`, `ExpertOpinion`, `LikertDecision`

**Characteristics**:
- Immutability enforced through `__slots__` and attribute protection
- Equality based on values, not identity
- Hashable for use in sets and dictionaries

**Benefits**:
- Thread-safe without synchronization
- Predictable behavior (no side effects)
- Suitable for use as dictionary keys

### 2. Strategy Pattern

**Applied in**: `MedianCalculationStrategy` with `OddMedianStrategy` and `EvenMedianStrategy`

**Characteristics**:
- Abstract strategy interface
- Concrete strategies for different expert counts
- Runtime strategy selection based on context

**Benefits**:
- Open/Closed Principle compliance
- Easy to add new median calculation strategies
- Testable in isolation

### 3. Template Method Pattern

**Applied in**: `BaseAggregationCalculator`

**Characteristics**:
- Abstract base class defines algorithm skeleton
- Concrete implementations provide specific steps
- Enforces consistent interface across implementations

**Benefits**:
- Code reuse through inheritance
- Consistent behavior across calculators
- Clear contract for implementers

### 4. Factory Method Pattern

**Applied in**: `BeCoMeResult.from_calculations()`

**Characteristics**:
- Static factory method encapsulates object creation
- Handles complex initialization logic
- Derives additional fields automatically

**Benefits**:
- Simplified object construction
- Validation at creation time
- Single source of truth for result derivation

## Type Safety

All source code maintains strict type safety:

- **Type hints**: All functions and methods have complete type annotations
- **mypy strict mode**: Zero type errors in strict checking mode
- **No `type: ignore`**: All type issues resolved without suppressions
- **Runtime validation**: Pydantic models validate at runtime

**Type checking**:
```bash
uv run mypy src/
```

## Immutability

All data models are immutable to ensure predictable behavior:

**Techniques used**:
- `__slots__` to prevent dynamic attribute assignment
- `__setattr__` and `__delattr__` overrides to block modifications
- Pydantic `frozen=True` for model immutability
- Properties for read-only access to internal state

**Benefits**:
- Thread-safe without locks
- Hashable and usable in sets/dicts
- Easier to reason about (no hidden state changes)
- Prevents bugs from unintended mutations

## Importing Modules

All imports should use absolute paths from the project root:

```python
# Correct (absolute imports)
from src.models.fuzzy_number import FuzzyTriangleNumber
from src.models.expert_opinion import ExpertOpinion
from src.models.become_result import BeCoMeResult
from src.calculators.become_calculator import BeCoMeCalculator
from src.interpreters.likert_interpreter import LikertDecisionInterpreter
from src.exceptions import BeCoMeError, EmptyOpinionsError

# Incorrect (relative imports from outside package)
from models.fuzzy_number import FuzzyTriangleNumber  # Will fail
```

**Note**: Internal relative imports within `src/` modules are acceptable (e.g., in `expert_opinion.py` importing from `.fuzzy_number`).

## Dependencies

The core implementation has minimal external dependencies:

**Required**:
- Python 3.13+ (standard library)
- `pydantic` - For validated data models (`BeCoMeResult`)

**Development**:
- `mypy` - Static type checking
- `pytest` - Testing framework
- `ruff` - Linting and formatting

**Philosophy**: Minimize external dependencies to reduce attack surface and improve reproducibility.

## Code Quality Standards

The implementation maintains strict quality standards for academic work:

### Code Coverage

- **Target**: 100% line and branch coverage
- **Current**: 100% (all source lines covered by tests)
- **Test location**: [../tests/](../tests/)

### Type Safety

- **Tool**: mypy in strict mode
- **Status**: Zero type errors
- **Compliance**: 100% (no `type: ignore` comments)

### Code Style

- **Tool**: ruff (linter and formatter)
- **Compliance**: 100% (all rules passing)
- **Standards**: PEP 8, PEP 257 (docstrings)

### Documentation

- **Coverage**: 100% of public APIs documented
- **Style**: Google-style docstrings with type annotations
- **Examples**: Included in docstrings where applicable

## Testing

The implementation is validated through comprehensive tests:

### Test Organization

- **Unit tests**: [../tests/unit/models/](../tests/unit/models/), [../tests/unit/calculators/](../tests/unit/calculators/), [../tests/unit/interpreters/](../tests/unit/interpreters/)
- **Integration tests**: [../tests/integration/](../tests/integration/)
- **Reference validation**: Excel implementation comparison

### Running Tests

```bash
# All tests for src/
uv run pytest tests/unit/models/
uv run pytest tests/unit/calculators/
uv run pytest tests/unit/interpreters/

# With coverage
uv run pytest --cov=src tests/
```

See [../tests/README.md](../tests/README.md) for detailed testing documentation.

## Implementation Notes

### Mathematical Notation

The code uses Greek letters in comments to match the mathematical notation from the BeCoMe method specification:

- Γ (Gamma) - Arithmetic mean
- Ω (Omega) - Statistical median
- Δ (Delta) - Maximum error
- α, γ, β (alpha, gamma, beta) - Components of arithmetic mean
- ρ, ω, σ (rho, omega, sigma) - Components of median
- π, φ, ξ (pi, phi, xi) - Components of best compromise

**Note**: Variable names in code use English (e.g., `arithmetic_mean`, `median`) while comments reference mathematical symbols for traceability to source material.

### Numerical Precision

- Calculations use Python `float` (IEEE 754 double precision)
- Validation against Excel reference implementation uses tolerance: 0.001
- No rounding applied during calculations (only in display formatting)

### Performance Considerations

- Immutable data structures reduce memory overhead through sharing
- `__slots__` reduces memory footprint for value objects
- Sorting is stable (maintains original order for equal centroids)
- No premature optimization (clarity prioritized over performance)

## Related Documentation

For additional information about the BeCoMe implementation:

- **Main README**: [../README.md](../README.md) - Project overview and installation
- **Documentation index**: [../docs/README.md](../docs/README.md) - Complete documentation navigation
- **Method description**: [../docs/method-description.md](../docs/method-description.md) - Mathematical foundation
- **API reference**: [../docs/api-reference.md](../docs/api-reference.md) - Complete API documentation
- **Architecture**: [../docs/architecture.md](../docs/architecture.md) - Design decisions and rationale
- **UML diagrams**: [../docs/uml-diagrams.md](../docs/uml-diagrams.md) - Visual architecture
- **References**: [../docs/references.md](../docs/references.md) - Bibliography and cited sources
- **Tests**: [../tests/README.md](../tests/README.md) - Testing methodology and coverage
- **Examples**: [../examples/README.md](../examples/README.md) - Usage examples and case studies

## Contributing to the Codebase

This implementation is part of a bachelor thesis and follows strict academic standards:

### Code Modification Guidelines

1. **Maintain type safety**: All new code must pass `mypy --strict`
2. **Preserve immutability**: Data models must remain immutable
3. **Add tests**: 100% coverage required for all new code
4. **Document thoroughly**: Complete docstrings with parameter types
5. **Follow patterns**: Use existing design patterns consistently
6. **Validate against Excel**: Ensure calculations match reference implementation

### Before Submitting Changes

```bash
# Type checking
uv run mypy src/

# Linting
uv run ruff check src/

# Formatting
uv run ruff format src/

# Tests with coverage
uv run pytest --cov=src --cov-report=term-missing tests/
```

## License

This implementation is part of a bachelor thesis at the Faculty of Economics and Management, Czech University of Life Sciences Prague. See [../README.md](../README.md) for complete license and academic use information.
