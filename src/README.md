# BeCoMe source code

Core implementation of the BeCoMe method for aggregating expert opinions expressed as fuzzy triangular numbers.

## Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Module descriptions](#module-descriptions)
- [Design patterns](#design-patterns)
- [Type safety](#type-safety)
- [Importing modules](#importing-modules)
- [Dependencies](#dependencies)
- [Testing](#testing)
- [Usage with examples](#usage-with-examples)
- [Related documentation](#related-documentation)
- [Contributing](#contributing)

## Overview

Three layers handle different responsibilities. **Models** define the immutable data structures:
fuzzy numbers, expert opinions, and calculation results. **Calculators** hold the aggregation
logic for the arithmetic mean, the median, and the best compromise. **Interpreters** translate a
result into decision-making language through a Likert scale mapping.

The code passes mypy in strict mode and has 100% test coverage.

## Architecture

### Layered structure

```
src/
├── models/              # Domain models (Value Objects)
│   ├── fuzzy_number.py       # Fuzzy triangular number representation
│   ├── expert_opinion.py     # Expert opinion with identifier
│   └── become_result.py      # Calculation result (Pydantic model)
├── calculators/         # Calculation logic
│   ├── base_calculator.py        # Abstract base class (the shared interface)
│   ├── median_strategies.py     # Median calculation strategies (Strategy Pattern)
│   └── become_calculator.py     # Main BeCoMe implementation
├── interpreters/        # Result interpretation
│   └── likert_interpreter.py    # Likert scale decision interpreter
├── exceptions.py        # Custom exception hierarchy
└── __init__.py         # Package marker
```

### Dependency flow

```
interpreters/
    ↓
calculators/
    ↓
models/
    ↓
exceptions.py
```

Components depend only on the layers below them, so a lower layer can be tested without the
ones above it.

## Module descriptions

### Models layer (`models/`)

#### [fuzzy_number.py](https://github.com/caitlon/BeCoMe/blob/main/src/models/fuzzy_number.py)

`FuzzyTriangleNumber` represents a triangular fuzzy number (lower_bound, peak, upper_bound). The class validates that lower ≤ peak ≤ upper and calculates the centroid as
(lower + peak + upper) / 3. `__slots__` and an overridden `__setattr__` enforce immutability.

```python
from src.models.fuzzy_number import FuzzyTriangleNumber

fuzzy = FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0)
print(fuzzy.centroid)  # 15.0

# Average multiple fuzzy numbers
avg = FuzzyTriangleNumber.average([fuzzy1, fuzzy2])
```

#### [expert_opinion.py](https://github.com/caitlon/BeCoMe/blob/main/src/models/expert_opinion.py)

`ExpertOpinion` pairs an expert ID with that expert's fuzzy assessment. Opinions compare by
centroid, so sorting them puts the median in the middle.

```python
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

opinion = ExpertOpinion("Expert1", FuzzyTriangleNumber(10.0, 15.0, 20.0))
opinions_sorted = sorted([opinion1, opinion2, opinion3])  # by centroid
```

#### [become_result.py](https://github.com/caitlon/BeCoMe/blob/main/src/models/become_result.py)

`BeCoMeResult` is a Pydantic model holding the calculation outputs: best compromise (ΓΩMean), arithmetic mean (Γ), median (Ω), and maximum error (Δmax). The factory method `from_calculations()` derives the best compromise and error automatically.

```python
from src.models.become_result import BeCoMeResult

result = BeCoMeResult.from_calculations(
    arithmetic_mean=mean_fuzzy, median=median_fuzzy, num_experts=22
)
print(result.best_compromise)
print(result.max_error)
```

### Calculators layer (`calculators/`)

#### [base_calculator.py](https://github.com/caitlon/BeCoMe/blob/main/src/calculators/base_calculator.py)

`BaseAggregationCalculator` defines the interface: `calculate_arithmetic_mean()`,
`calculate_median()`, `calculate_compromise()`, and `sort_by_centroid()`. All four are
abstract, so a subclass supplies every one of them.

#### [median_strategies.py](https://github.com/caitlon/BeCoMe/blob/main/src/calculators/median_strategies.py)

Median calculation differs for odd and even expert counts. `OddMedianStrategy` returns the middle element after sorting. `EvenMedianStrategy` averages the two middle elements. The calculator selects the strategy at runtime, from the expert count.

```python
from src.calculators.median_strategies import OddMedianStrategy, EvenMedianStrategy

strategy = OddMedianStrategy() if m % 2 == 1 else EvenMedianStrategy()
median = strategy.calculate(sorted_opinions)
```

#### [become_calculator.py](https://github.com/caitlon/BeCoMe/blob/main/src/calculators/become_calculator.py)

Main BeCoMe implementation. Arithmetic mean (Γ) averages lower bounds, peaks, and upper bounds separately. Median (Ω) sorts opinions by centroid and applies the matching strategy. Best compromise (ΓΩMean) averages mean and median component-wise. Maximum error (Δmax) is half the distance between mean and median centroids.

```python
from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

calculator = BeCoMeCalculator()
opinions = [
    ExpertOpinion("E1", FuzzyTriangleNumber(10, 15, 20)),
    ExpertOpinion("E2", FuzzyTriangleNumber(12, 18, 24)),
    ExpertOpinion("E3", FuzzyTriangleNumber(8, 13, 18)),
]
result = calculator.calculate_compromise(opinions)
```

### Interpreters layer (`interpreters/`)

#### [likert_interpreter.py](https://github.com/caitlon/BeCoMe/blob/main/src/interpreters/likert_interpreter.py)

`LikertDecisionInterpreter` maps fuzzy number centroids to a 5-point Likert scale
(0, 25, 50, 75, 100) and generates the decision text. It is what the Pendlers case needs, where
experts rated policies on an ordinal scale.

```python
from src.interpreters.likert_interpreter import LikertDecisionInterpreter

interpreter = LikertDecisionInterpreter()
decision = interpreter.interpret(result.best_compromise)
print(decision.likert_value)  # 75
print(decision.decision_text)  # "Rather agree"
```

### Exception hierarchy (`exceptions.py`)

`BeCoMeError` is the base. The calculator raises `EmptyOpinionsError` when the opinion list is
empty, `InvalidOpinionError` for malformed input, and `CalculationError` for a failure during
aggregation.

```python
from src.exceptions import EmptyOpinionsError

try:
    result = calculator.calculate_compromise([])
except EmptyOpinionsError as e:
    print(f"Error: {e}")
```

## Design patterns

**Value object.** `FuzzyTriangleNumber`, `ExpertOpinion`, and `LikertDecision` are immutable.
The first two use `__slots__` and override `__setattr__` to block modification, and
`LikertDecision` is a frozen dataclass. All three are hashable, so they can serve as dictionary
keys.

**Strategy.** Median calculation has two variants, one for an odd expert count and one for an
even count. `MedianCalculationStrategy` is the interface, and `OddMedianStrategy` and
`EvenMedianStrategy` are the concrete implementations. The calculator picks one at runtime.

**Abstract interface.** `BaseAggregationCalculator` is a pure ABC: all four methods are
abstract and it sequences nothing itself, so the calculation flow lives in
`BeCoMeCalculator`. What the base class buys is one shape for every aggregation method
added later.

**Factory method.** `BeCoMeResult.from_calculations()` takes the arithmetic mean and the
median, then derives the best compromise and the maximum error. It keeps the construction logic
in one place.

## Type safety

Every function has type annotations, and the code passes `uv run mypy src/` in strict mode.
`src/` carries a single `type: ignore`, on `become_result.py:52`, where mypy and Pydantic's
`@computed_field` decorator disagree about the property type. Pydantic models also validate at
runtime.

## Importing modules

Use absolute paths from the project root for every import:

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

Relative imports inside `src/` are acceptable, for example `expert_opinion.py` importing from
`.fuzzy_number`.

## Dependencies

Runtime requires only Python 3.13+ and `pydantic` (for `BeCoMeResult` validation). Development adds `mypy`, `pytest`, and `ruff`. The calculation logic itself uses no external libraries.

## Testing

Unit tests live in `tests/unit/` (models, calculators, interpreters). Integration tests in `tests/integration/` validate results against the original Excel implementation.

```bash
uv run pytest tests/unit/
uv run pytest --cov=src tests/
```

See [../tests/README.md](https://docs.becomify.app/dev/testing/) for details.

## Usage with examples

The `examples/` directory shows how to use this code with real case studies. Each example loads data, calls `BeCoMeCalculator`, and displays step-by-step results. See [../examples/README.md](https://docs.becomify.app/dev/examples/).

## Related documentation

- [Main README](https://docs.becomify.app/): project overview
- [Method description](https://docs.becomify.app/method-description/): mathematical foundation
- [UML diagrams](https://docs.becomify.app/uml-diagrams/): visual architecture
- [Tests](https://docs.becomify.app/dev/testing/): test organization
- [Examples](https://docs.becomify.app/dev/examples/): case studies

## Contributing

New code must pass mypy strict mode, keep the data models immutable, and hold `src/` at 100%
coverage. Run all three checks before submitting:

```bash
uv run mypy src/
uv run ruff check src/
uv run pytest --cov=src tests/
```
