# BeCoMe Source Code

Core implementation of the BeCoMe method for aggregating expert opinions expressed as fuzzy triangular numbers.

## Overview

Three layers handle different responsibilities. **Models** define immutable data structures — fuzzy numbers, expert opinions, calculation results. **Calculators** contain the aggregation logic: arithmetic mean, median, and best compromise. **Interpreters** translate results into decision-making language (Likert scale mapping).

The code passes mypy in strict mode and has 100% test coverage.

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

#### [fuzzy_number.py](models/fuzzy_number.py)

`FuzzyTriangleNumber` represents a triangular fuzzy number (lower_bound, peak, upper_bound). The class validates that lower ≤ peak ≤ upper and calculates the centroid as (lower + peak + upper) / 3. Immutability is enforced through `__slots__`.

```python
from src.models.fuzzy_number import FuzzyTriangleNumber

fuzzy = FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0)
print(fuzzy.centroid)  # 15.0

# Average multiple fuzzy numbers
avg = FuzzyTriangleNumber.average([fuzzy1, fuzzy2])
```

#### [expert_opinion.py](models/expert_opinion.py)

`ExpertOpinion` pairs an expert ID with their fuzzy assessment. Opinions are comparable by centroid, which enables sorting for median calculation.

```python
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

opinion = ExpertOpinion("Expert1", FuzzyTriangleNumber(10.0, 15.0, 20.0))
opinions_sorted = sorted([opinion1, opinion2, opinion3])  # by centroid
```

#### [become_result.py](models/become_result.py)

`BeCoMeResult` is a Pydantic model holding the calculation outputs: best compromise (ΓΩMean), arithmetic mean (Γ), median (Ω), and maximum error (Δmax). The factory method `from_calculations()` derives the best compromise and error automatically.

```python
from src.models.become_result import BeCoMeResult

result = BeCoMeResult.from_calculations(
    arithmetic_mean=mean_fuzzy,
    median=median_fuzzy,
    num_experts=22
)
print(result.best_compromise)
print(result.max_error)
```

### Calculators Layer (`calculators/`)

#### [base_calculator.py](calculators/base_calculator.py)

`BaseAggregationCalculator` defines the interface: `calculate_arithmetic_mean()`, `calculate_median()`, `calculate_compromise()`, and `sort_by_centroid()`. Template Method pattern — subclasses implement the actual logic.

#### [median_strategies.py](calculators/median_strategies.py)

Median calculation differs for odd and even expert counts. `OddMedianStrategy` returns the middle element after sorting. `EvenMedianStrategy` averages the two middle elements. The calculator selects the strategy at runtime based on expert count.

```python
from src.calculators.median_strategies import OddMedianStrategy, EvenMedianStrategy

strategy = OddMedianStrategy() if m % 2 == 1 else EvenMedianStrategy()
median = strategy.calculate(sorted_opinions, median_centroid)
```

#### [become_calculator.py](calculators/become_calculator.py)

Main BeCoMe implementation. Arithmetic mean (Γ) averages lower bounds, peaks, and upper bounds separately. Median (Ω) sorts opinions by centroid and applies the appropriate strategy. Best compromise (ΓΩMean) averages mean and median component-wise. Maximum error (Δmax) is half the distance between mean and median centroids.

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

#### [likert_interpreter.py](interpreters/likert_interpreter.py)

`LikertDecisionInterpreter` maps fuzzy number centroids to a 5-point Likert scale (0, 25, 50, 75, 100) and generates decision text. Useful for the Pendlers case where experts rated policies on an ordinal scale.

```python
from src.interpreters.likert_interpreter import LikertDecisionInterpreter

interpreter = LikertDecisionInterpreter()
decision = interpreter.interpret(result.best_compromise)
print(decision.likert_value)      # 75
print(decision.decision_text)     # "Rather agree"
```

### Exception Hierarchy (`exceptions.py`)

`BeCoMeError` is the base. `EmptyOpinionsError` is raised when the opinion list is empty. `InvalidOpinionError` catches malformed input. `CalculationError` covers failures during aggregation.

```python
from src.exceptions import EmptyOpinionsError

try:
    result = calculator.calculate_compromise([])
except EmptyOpinionsError as e:
    print(f"Error: {e}")
```

## Design Patterns

**Value Object** — `FuzzyTriangleNumber`, `ExpertOpinion`, and `LikertDecision` are immutable. They use `__slots__` and override `__setattr__` to prevent modification. Being hashable, they can serve as dictionary keys.

**Strategy** — Median calculation has two variants (odd/even expert counts). `MedianCalculationStrategy` is the interface; `OddMedianStrategy` and `EvenMedianStrategy` are the concrete implementations. The calculator picks one at runtime.

**Template Method** — `BaseAggregationCalculator` defines the calculation flow. Subclasses fill in the steps. This keeps the interface consistent if someone adds a different aggregation method later.

**Factory Method** — `BeCoMeResult.from_calculations()` takes arithmetic mean and median, then derives the best compromise and maximum error automatically. Keeps construction logic in one place.

## Type Safety

Every function has type annotations. The code passes `uv run mypy src/` in strict mode with no `type: ignore` comments. Pydantic models also validate at runtime.

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

Runtime requires only Python 3.13+ and `pydantic` (for `BeCoMeResult` validation). Development adds `mypy`, `pytest`, and `ruff`. The calculation logic itself uses no external libraries.

## Testing

Unit tests live in `tests/unit/` (models, calculators, interpreters). Integration tests in `tests/integration/` validate results against the original Excel implementation.

```bash
uv run pytest tests/unit/
uv run pytest --cov=src tests/
```

See [../tests/README.md](../tests/README.md) for details.

## Usage with Examples

The `examples/` directory shows how to use this code with real case studies. Each example loads data, calls `BeCoMeCalculator`, and displays step-by-step results. See [../examples/README.md](../examples/README.md).

## Related Documentation

- [Main README](../README.md) — project overview
- [Method description](../docs/method-description.md) — mathematical foundation
- [UML diagrams](../docs/uml-diagrams/en/README.md) — visual architecture
- [Tests](../tests/README.md) — test organization
- [Examples](../examples/README.md) — case studies

## Contributing

New code must pass mypy strict mode, maintain immutability for data models, and have test coverage. Run all checks before submitting:

```bash
uv run mypy src/
uv run ruff check src/
uv run pytest --cov=src tests/
```
