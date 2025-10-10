# Architecture & Design Decisions

This document explains the architectural choices and design decisions made in the BeCoMe implementation.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Design Principles](#design-principles)
3. [Module Structure](#module-structure)
4. [Design Patterns](#design-patterns)
5. [Technology Choices](#technology-choices)
6. [Design Decisions](#design-decisions)
7. [Trade-offs](#trade-offs)
8. [Future Considerations](#future-considerations)

---

## Architecture Overview

### Layered Architecture

The implementation follows a clean layered architecture:

```
┌─────────────────────────────────────┐
│         Examples Layer              │  ← User-facing examples
│  (analyze_*.py, utils.py)          │
└─────────────────────────────────────┘
           ↓ uses
┌─────────────────────────────────────┐
│       Calculator Layer              │  ← Business logic
│  (BeCoMeCalculator)                │
└─────────────────────────────────────┘
           ↓ uses
┌─────────────────────────────────────┐
│         Models Layer                │  ← Domain models
│  (FuzzyTriangleNumber,             │
│   ExpertOpinion, BeCoMeResult)     │
└─────────────────────────────────────┘
```

### Key Characteristics

- **Separation of Concerns**: Models, calculators, and examples are clearly separated
- **Dependency Direction**: Dependencies flow downward (examples → calculators → models)
- **No Circular Dependencies**: Clean dependency graph
- **Testable**: Each layer can be tested independently

---

## Design Principles

### 1. SOLID Principles

#### Single Responsibility Principle (SRP)
Each class has one clear responsibility:
- `FuzzyTriangleNumber` - represents a fuzzy number
- `ExpertOpinion` - represents an expert's opinion
- `BeCoMeCalculator` - performs calculations
- `BeCoMeResult` - stores results

#### Open/Closed Principle (OCP)
- Classes are open for extension (can be subclassed)
- Closed for modification (stable public APIs)
- Example: `BeCoMeCalculator` can be extended with additional aggregation methods

#### Liskov Substitution Principle (LSP)
- Not heavily used (minimal inheritance)
- `ExpertOpinion` dataclass is substitutable in all contexts

#### Interface Segregation Principle (ISP)
- Classes expose minimal, focused interfaces
- No "fat" interfaces with unnecessary methods

#### Dependency Inversion Principle (DIP)
- Calculators depend on abstract models, not concrete implementations
- Easy to swap implementations (e.g., different fuzzy number types)

### 2. DRY (Don't Repeat Yourself)

- Centroid calculation implemented once in `FuzzyTriangleNumber`
- Sorting logic reused via `_sort_by_centroid()` helper
- Validation logic centralized in model constructors

### 3. KISS (Keep It Simple, Stupid)

- No unnecessary abstractions or frameworks
- Straightforward class hierarchy
- Direct implementation of mathematical formulas
- Simple is better than complex

### 4. YAGNI (You Aren't Gonna Need It)

- No premature optimization
- No unused features
- Only implemented what the BeCoMe paper specifies
- Example: No trapezoidal or Gaussian fuzzy numbers (not needed)

---

## Module Structure

### Rationale for Structure

```
src/
├── models/              # Domain models (data structures)
│   ├── fuzzy_number.py
│   ├── expert_opinion.py
│   └── become_result.py
└── calculators/         # Business logic
    └── become_calculator.py
```

**Why this structure?**

1. **Clear separation**: Models vs. logic
2. **Scalability**: Easy to add new calculators or models
3. **Discoverability**: Intuitive for new developers
4. **Python conventions**: Follows common Python project layouts

### Not Chosen Alternatives

❌ **Flat structure** (all files in `src/`)
- Would become messy as project grows
- Harder to navigate

❌ **Over-engineered structure** (e.g., `src/domain/entities/`, `src/infrastructure/`, etc.)
- Too complex for this size of project
- Violates KISS principle

---

## Design Patterns

### 1. Composition over Inheritance

**Pattern:** `ExpertOpinion` *contains* a `FuzzyTriangleNumber`

```python
@dataclass
class ExpertOpinion:
    expert_id: str
    opinion: FuzzyTriangleNumber  # Composition
```

**Why composition?**
- More flexible than inheritance
- `ExpertOpinion` IS-NOT-A `FuzzyTriangleNumber`
- `ExpertOpinion` HAS-A `FuzzyTriangleNumber`
- Enables delegation (e.g., `get_centroid()`)

**Alternative considered:**
- Inheritance (`class ExpertOpinion(FuzzyTriangleNumber)`)
- ❌ Rejected: Violates IS-A relationship, tight coupling

### 2. Value Object Pattern

**Pattern:** `FuzzyTriangleNumber` is an immutable value object

```python
class FuzzyTriangleNumber:
    def __init__(self, lower_bound: float, peak: float, upper_bound: float):
        # Validation
        self.lower_bound = lower_bound  # Immutable after construction
        self.peak = peak
        self.upper_bound = upper_bound
```

**Why immutable?**
- Mathematical values shouldn't change
- Thread-safe
- Easier to reason about
- Prevents accidental mutations

**Note:** Python doesn't enforce immutability strictly, but convention + Pydantic helps

### 3. Data Transfer Object (DTO) Pattern

**Pattern:** `BeCoMeResult` is a DTO using Pydantic

```python
class BeCoMeResult(BaseModel):
    best_compromise: FuzzyTriangleNumber
    arithmetic_mean: FuzzyTriangleNumber
    # ... other fields
```

**Why Pydantic?**
- Automatic validation
- Type checking at runtime
- Serialization (JSON, dict) for free
- Great for API responses or data exchange

### 4. Strategy Pattern (Implicit)

**Pattern:** Calculator methods represent different aggregation strategies

```python
class BeCoMeCalculator:
    def calculate_arithmetic_mean(self, opinions): ...  # Strategy 1
    def calculate_median(self, opinions): ...           # Strategy 2
    def calculate_compromise(self, opinions): ...       # Combined strategy
```

**Why separate methods?**
- Users can choose which aggregation to use
- Easy to test each strategy independently
- Flexible: can use mean-only or median-only if needed

### 5. Factory Pattern (Implicit)

**Pattern:** Calculator creates result objects

```python
def calculate_compromise(self, opinions) -> BeCoMeResult:
    # ... calculations ...
    return BeCoMeResult(  # Factory method
        best_compromise=...,
        arithmetic_mean=...,
        # ...
    )
```

**Why?**
- Centralizes result creation
- Ensures all fields are populated correctly
- Hides complexity of result construction

---

## Technology Choices

### Python 3.13+

**Why Python?**
- ✓ Excellent for scientific computing
- ✓ Rich ecosystem (NumPy, pandas)
- ✓ Clear, readable syntax
- ✓ Strong typing support (3.10+)
- ✓ Good for academic/research projects

**Why 3.13+?**
- Modern type hints (`list[T]` instead of `List[T]`)
- Better performance
- Latest features

### Pydantic

**Why Pydantic for `BeCoMeResult`?**
- ✓ Runtime validation
- ✓ Automatic JSON serialization
- ✓ Clear error messages
- ✓ Great IDE support
- ✓ Industry standard for data validation

**Alternative considered:**
- `@dataclass` (built-in)
- ❌ No validation, no serialization

### Dataclass for `ExpertOpinion`

**Why `@dataclass` instead of Pydantic?**
- ✓ Simpler, built-in
- ✓ No validation needed (composition with validated `FuzzyTriangleNumber`)
- ✓ Automatic `__init__`, `__repr__`, `__eq__`
- ✓ Supports comparison operators (`@dataclass(order=True)` if needed)

### Plain Class for `FuzzyTriangleNumber`

**Why plain class instead of dataclass?**
- ✓ Need custom `__init__` with validation
- ✓ Need custom comparison logic (centroid-based)
- ✓ More control over behavior
- ✓ Clearer for mathematical concepts

### No NumPy in Core Logic

**Why no NumPy arrays for fuzzy numbers?**
- ✓ Simple float operations are sufficient
- ✓ Avoid dependency bloat
- ✓ Clear, readable formulas
- ✓ No vectorization needed (small M)

**When NumPy is used:**
- Only in tests for data loading (Excel)
- Not in core implementation

### Testing Stack: pytest

**Why pytest?**
- ✓ Industry standard
- ✓ Clean syntax (`assert` instead of `self.assertEqual`)
- ✓ Powerful fixtures
- ✓ Great plugin ecosystem (coverage, parametrize)

### Linting: ruff + mypy

**Why ruff?**
- ✓ Fast (Rust-based)
- ✓ Replaces many tools (flake8, isort, black)
- ✓ Configurable
- ✓ Modern

**Why mypy?**
- ✓ Industry standard for type checking
- ✓ Catches type errors at development time
- ✓ Works well with strict mode

---

## Design Decisions

### Decision 1: Centroid-Based Sorting

**Choice:** Sort opinions by centroid for median calculation

**Rationale:**
- Centroid represents the "center of mass" of the fuzzy number
- Mathematically sound measure of central tendency
- Specified in original BeCoMe paper
- Stable (unique value for each fuzzy number)

**Alternative considered:**
- Peak-based sorting
- ❌ Rejected: Different fuzzy numbers can have same peak

### Decision 2: Separate Methods for Mean and Median

**Choice:** `calculate_arithmetic_mean()` and `calculate_median()` are separate

**Rationale:**
- Users might want only mean or only median
- Easier to test each separately
- Clear API (each method does one thing)
- Follows SRP

**Alternative considered:**
- Single method that returns tuple `(mean, median)`
- ❌ Rejected: Less flexible, harder to test

### Decision 3: Private `_sort_by_centroid()` Helper

**Choice:** Sorting logic is a private method

**Rationale:**
- Implementation detail, not part of public API
- Prevents misuse
- Can change implementation without breaking users
- Follows encapsulation principle

**Alternative considered:**
- Public method
- ❌ Rejected: Not part of BeCoMe algorithm, just a helper

### Decision 4: Validation in Constructor

**Choice:** `FuzzyTriangleNumber` validates in `__init__`

**Rationale:**
- Fail fast (catch errors early)
- Invalid fuzzy numbers never exist
- Clear error messages at creation time
- Defensive programming

**Alternative considered:**
- Validation in calculator methods
- ❌ Rejected: Too late, allows invalid state

### Decision 5: Immutable Models

**Choice:** Models don't have setter methods

**Rationale:**
- Mathematical values shouldn't change
- Prevents bugs from accidental mutations
- Thread-safe
- Easier reasoning about state

**Alternative considered:**
- Mutable models with setters
- ❌ Rejected: Unnecessary complexity, risk of bugs

### Decision 6: Type Hints Everywhere

**Choice:** All functions have complete type hints

**Rationale:**
- Better IDE support (autocomplete, refactoring)
- Catches errors at development time (mypy)
- Self-documenting code
- Python best practice (PEP 484)

**Alternative considered:**
- No type hints (dynamic Python)
- ❌ Rejected: Harder to maintain, more bugs

### Decision 7: Pydantic for Result, Dataclass for Opinion

**Choice:** Different validation strategies for different needs

**Rationale:**
- `BeCoMeResult`: Complex, needs validation, serialization → Pydantic
- `ExpertOpinion`: Simple, composition-based → dataclass
- Right tool for the job

**Alternative considered:**
- Pydantic for everything
- ❌ Rejected: Overkill for simple `ExpertOpinion`

### Decision 8: No Abstract Base Classes

**Choice:** No ABC or interfaces

**Rationale:**
- YAGNI: Only one implementation of each class
- Python duck typing works well
- Simpler codebase
- Easy to add later if needed

**Alternative considered:**
- Abstract base classes for extensibility
- ❌ Rejected: Premature abstraction

---

## Trade-offs

### 1. Simplicity vs. Flexibility

**Choice:** Simplicity

**Trade-off:**
- ✓ Easy to understand and use
- ✗ Harder to extend (e.g., add new fuzzy number types)

**Justification:** For a research/thesis project, clarity > extensibility

### 2. Performance vs. Readability

**Choice:** Readability

**Trade-off:**
- ✓ Code directly matches mathematical formulas
- ✗ Not optimized for large M (but sufficient for typical use)

**Justification:** BeCoMe is typically used with 3-30 experts, not thousands

### 3. Type Safety vs. Brevity

**Choice:** Type safety

**Trade-off:**
- ✓ Catches errors early, better IDE support
- ✗ More verbose code

**Justification:** Long-term maintainability > short-term convenience

### 4. Validation Strictness vs. Flexibility

**Choice:** Strict validation

**Trade-off:**
- ✓ Invalid states impossible
- ✗ Might reject edge cases (e.g., `lower_bound == peak == upper_bound`)

**Justification:** Mathematical correctness > edge case flexibility

**Note:** Edge cases like crisp values (A = C = B) are actually valid and supported

---

## Future Considerations

### Potential Extensions (Not Implemented Yet)

#### 1. Alternative Fuzzy Number Types

```python
class FuzzyNumber(ABC):  # Abstract base
    @abstractmethod
    def get_centroid(self) -> float: ...

class FuzzyTriangleNumber(FuzzyNumber): ...
class FuzzyTrapezoidalNumber(FuzzyNumber): ...
```

**Why not now?** YAGNI - BeCoMe paper only uses triangular

#### 2. Weighted Experts

```python
@dataclass
class WeightedExpertOpinion(ExpertOpinion):
    weight: float = 1.0
```

**Why not now?** Original BeCoMe doesn't use weights

#### 3. Alternative Aggregation Methods

```python
class BeCoMeCalculator:
    def calculate_geometric_mean(self, opinions): ...
    def calculate_harmonic_mean(self, opinions): ...
```

**Why not now?** Not part of BeCoMe method

#### 4. Visualization

```python
def plot_fuzzy_number(fuzzy: FuzzyTriangleNumber) -> None:
    # matplotlib plot
```

**Why not now?** Scope limited to calculation, not visualization

#### 5. Batch Processing

```python
def calculate_multiple_cases(
    cases: dict[str, list[ExpertOpinion]]
) -> dict[str, BeCoMeResult]:
    # Process multiple cases
```

**Why not now?** Can be done with simple loop in user code

---

## Testing Strategy

### Test Structure

```
tests/
├── models/              # Unit tests for models
├── calculators/         # Unit tests for calculators
├── integration/         # Integration tests (Excel reference)
└── examples/           # Example data loading tests
```

### Test Coverage Goals

- **Target:** >95% code coverage
- **Current:** 100% (as of 2025-10-10)
- **Strategy:** Test all public methods + edge cases

### Testing Principles

1. **Unit tests for each class**
   - Test normal cases
   - Test edge cases
   - Test error conditions

2. **Integration tests**
   - Verify against Excel reference implementation
   - Test complete workflows
   - Test with real case study data

3. **Property-based testing**
   - Mathematical properties (e.g., mean ≤ max(opinions))
   - Invariants (e.g., result is always valid fuzzy number)

---

## Code Quality Standards

### Style Guide

- **PEP 8**: Python style guide
- **ruff**: Linting and formatting
- **Line length**: 100 characters
- **Docstrings**: All public APIs documented
- **Type hints**: All functions and methods

### Quality Checks

```bash
# Type checking
mypy src/

# Linting and formatting
ruff check .
ruff format .

# Testing
pytest --cov=src --cov-report=term-missing
```

### Documentation Standards

- **README**: Quick start and overview
- **API Reference**: Complete API documentation
- **Method Description**: Mathematical foundation
- **UML Diagrams**: Visual architecture
- **This document**: Design decisions

---

## Lessons Learned

### What Worked Well

✓ **Simple architecture** - Easy to understand and maintain  
✓ **Type hints** - Caught many errors early  
✓ **Pydantic** - Excellent for validation and serialization  
✓ **Clear separation** - Models vs. calculators  
✓ **Comprehensive tests** - Confidence in correctness  

### What Could Be Improved

⚠ **More examples** - Could add more case studies  
⚠ **Visualization** - Plotting fuzzy numbers would be helpful  
⚠ **Performance profiling** - Not tested with large M  
⚠ **Documentation** - Could add more inline comments  

### If Starting Over

1. Would keep the same architecture ✓
2. Would add visualization from the start
3. Would write tests alongside implementation (TDD)
4. Would add more type hints in examples

---

## Comparison with Reference Implementation

### Differences

| Aspect | This Implementation | Reference Implementation |
|--------|---------------------|-------------------------|
| Language | Python 3.13 | Python (older) |
| Type hints | ✓ Complete | ✗ None |
| Validation | ✓ Pydantic + manual | ✗ Minimal |
| Testing | ✓ 100% coverage | ⚠ Basic tests |
| Documentation | ✓ Comprehensive | ⚠ Minimal |
| Architecture | ✓ Layered, clean | ⚠ Monolithic |

### Why Better?

- More maintainable
- Better tested
- Type-safe
- Well-documented
- Production-ready

---

## Conclusion

This implementation prioritizes:

1. **Correctness** - Matches BeCoMe paper exactly
2. **Clarity** - Code is easy to understand
3. **Maintainability** - Well-structured and documented
4. **Testability** - Comprehensive test suite
5. **Type safety** - Complete type hints

The architecture is simple but extensible, following Python best practices and SOLID principles.

---

## References

**Design patterns:**
- Gang of Four (GoF) Design Patterns
- Martin Fowler - Patterns of Enterprise Application Architecture

**Python best practices:**
- PEP 8 - Style Guide for Python Code
- PEP 484 - Type Hints
- Real Python - Best Practices

**Clean code:**
- Robert C. Martin - Clean Code
- Robert C. Martin - Clean Architecture

---

*Last updated: 2025-10-10*  
*Architecture version: 1.0*

