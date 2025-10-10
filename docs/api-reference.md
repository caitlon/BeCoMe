# API Reference

Complete API documentation for the BeCoMe (Best Compromise Mean) implementation.

---

## Table of Contents

1. [Models](#models)
   - [FuzzyTriangleNumber](#fuzzytrianglenumber)
   - [ExpertOpinion](#expertopinion)
   - [BeCoMeResult](#becomeresult)
2. [Calculators](#calculators)
   - [BeCoMeCalculator](#becomecalculator)
3. [Usage Examples](#usage-examples)

---

## Models

### FuzzyTriangleNumber

Represents a fuzzy triangular number with three characteristic values.

**Module:** `src.models.fuzzy_number`

#### Class Definition

```python
class FuzzyTriangleNumber:
    """
    Represents a fuzzy triangular number with three characteristic values.
    
    A fuzzy triangular number is defined by:
    - lower_bound (A): the minimum possible value
    - peak (C): the most likely value
    - upper_bound (B): the maximum possible value
    
    Constraint: lower_bound <= peak <= upper_bound
    """
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `lower_bound` | `float` | Minimum value of the fuzzy number (A) |
| `peak` | `float` | Most likely value of the fuzzy number (C) |
| `upper_bound` | `float` | Maximum value of the fuzzy number (B) |

#### Constructor

```python
def __init__(
    self,
    lower_bound: float,
    peak: float,
    upper_bound: float
) -> None
```

**Parameters:**
- `lower_bound` (float): Minimum value (A)
- `peak` (float): Most likely value (C)
- `upper_bound` (float): Maximum value (B)

**Raises:**
- `ValueError`: If the constraint `lower_bound <= peak <= upper_bound` is violated

**Example:**

```python
from src.models.fuzzy_number import FuzzyTriangleNumber

# Valid fuzzy number
fuzzy = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
print(fuzzy)  # (5.00, 10.00, 15.00)

# Invalid fuzzy number (raises ValueError)
try:
    invalid = FuzzyTriangleNumber(10.0, 5.0, 15.0)  # peak < lower_bound
except ValueError as e:
    print(f"Error: {e}")
```

#### Methods

##### `get_centroid()`

Calculate the centroid (center of gravity) of the fuzzy triangular number.

```python
def get_centroid(self) -> float
```

**Returns:**
- `float`: The centroid value

**Formula:**
```
Gx = (lower_bound + peak + upper_bound) / 3
```

**Example:**

```python
fuzzy = FuzzyTriangleNumber(5.0, 10.0, 15.0)
centroid = fuzzy.get_centroid()
print(centroid)  # 10.0
```

##### `__str__()`

Return human-readable string representation.

```python
def __str__(self) -> str
```

**Returns:**
- `str`: Formatted string with 2 decimal places

**Example:**

```python
fuzzy = FuzzyTriangleNumber(5.0, 10.0, 15.0)
print(str(fuzzy))  # "(5.00, 10.00, 15.00)"
```

##### `__repr__()`

Return technical string representation.

```python
def __repr__(self) -> str
```

**Returns:**
- `str`: String showing class name and attribute values

**Example:**

```python
fuzzy = FuzzyTriangleNumber(5.0, 10.0, 15.0)
print(repr(fuzzy))  # "FuzzyTriangleNumber(lower=5.0, peak=10.0, upper=15.0)"
```

---

### ExpertOpinion

Represents a single expert's opinion as a fuzzy triangular number.

**Module:** `src.models.expert_opinion`

#### Class Definition

```python
@dataclass
class ExpertOpinion:
    """
    Represents a single expert's opinion as a fuzzy triangular number.
    
    This class uses composition to combine an expert identifier with
    their fuzzy opinion. It supports comparison operations based on
    the centroid of the fuzzy number for sorting purposes.
    """
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `expert_id` | `str` | Unique identifier for the expert (e.g., name or ID) |
| `opinion` | `FuzzyTriangleNumber` | The expert's assessment as a fuzzy number |

#### Constructor

```python
@dataclass
class ExpertOpinion:
    expert_id: str
    opinion: FuzzyTriangleNumber
```

**Parameters:**
- `expert_id` (str): Unique identifier for the expert
- `opinion` (FuzzyTriangleNumber): The expert's fuzzy assessment

**Example:**

```python
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

opinion = ExpertOpinion(
    expert_id="Expert 1",
    opinion=FuzzyTriangleNumber(5.0, 10.0, 15.0)
)
print(opinion)
```

#### Methods

##### `get_centroid()`

Get the centroid of the expert's opinion.

```python
def get_centroid(self) -> float
```

**Returns:**
- `float`: The centroid value of the opinion

**Example:**

```python
opinion = ExpertOpinion("Expert 1", FuzzyTriangleNumber(5.0, 10.0, 15.0))
print(opinion.get_centroid())  # 10.0
```

##### Comparison Operations

ExpertOpinion supports comparison operations for sorting based on centroid values.

**Supported operators:**
- `<` (`__lt__`): Less than
- `<=` (`__le__`): Less than or equal
- `==` (`__eq__`): Equal

**Example:**

```python
opinion1 = ExpertOpinion("Expert 1", FuzzyTriangleNumber(5.0, 10.0, 15.0))
opinion2 = ExpertOpinion("Expert 2", FuzzyTriangleNumber(8.0, 12.0, 18.0))

# Compare by centroid
print(opinion1 < opinion2)   # True (10.0 < 13.33)
print(opinion1 == opinion1)  # True

# Sort opinions
opinions = [opinion2, opinion1]
sorted_opinions = sorted(opinions)  # [opinion1, opinion2]
```

---

### BeCoMeResult

Complete result of a BeCoMe calculation.

**Module:** `src.models.become_result`

#### Class Definition

```python
class BeCoMeResult(BaseModel):
    """
    Complete result of a BeCoMe calculation.
    
    The BeCoMe method calculates a best compromise between the arithmetic mean
    and statistical median of expert opinions. This class stores all intermediate
    and final results.
    """
```

This is a Pydantic model with automatic validation.

#### Attributes

| Attribute | Type | Description | Constraints |
|-----------|------|-------------|-------------|
| `best_compromise` | `FuzzyTriangleNumber` | Final result (ΓΩMean) | Required |
| `arithmetic_mean` | `FuzzyTriangleNumber` | Arithmetic mean (Γ) | Required |
| `median` | `FuzzyTriangleNumber` | Statistical median (Ω) | Required |
| `max_error` | `float` | Maximum error (Δmax) | ≥ 0 |
| `num_experts` | `int` | Number of expert opinions | ≥ 1 |
| `is_even` | `bool` | Whether number of experts is even | Required |

#### Constructor

```python
BeCoMeResult(
    best_compromise: FuzzyTriangleNumber,
    arithmetic_mean: FuzzyTriangleNumber,
    median: FuzzyTriangleNumber,
    max_error: float,
    num_experts: int,
    is_even: bool
)
```

**Parameters:**
- `best_compromise` (FuzzyTriangleNumber): Best compromise (ΓΩMean)
- `arithmetic_mean` (FuzzyTriangleNumber): Arithmetic mean (Γ)
- `median` (FuzzyTriangleNumber): Statistical median (Ω)
- `max_error` (float): Maximum error (Δmax), must be ≥ 0
- `num_experts` (int): Number of experts, must be ≥ 1
- `is_even` (bool): True if number of experts is even

**Raises:**
- `ValidationError`: If constraints are violated (Pydantic validation)

**Example:**

```python
from src.models.become_result import BeCoMeResult
from src.models.fuzzy_number import FuzzyTriangleNumber

result = BeCoMeResult(
    best_compromise=FuzzyTriangleNumber(10.0, 15.33, 21.17),
    arithmetic_mean=FuzzyTriangleNumber(10.0, 15.67, 22.33),
    median=FuzzyTriangleNumber(10.0, 15.0, 20.0),
    max_error=0.5,
    num_experts=3,
    is_even=False
)
print(result)
```

#### Methods

##### `__str__()`

Return human-readable string representation.

```python
def __str__(self) -> str
```

**Returns:**
- `str`: Formatted multi-line string with all results

**Example:**

```python
print(result)
# Output:
# BeCoMe Result (3 experts, odd):
#   Best Compromise: (10.00, 15.33, 21.17)
#   Arithmetic Mean: (10.00, 15.67, 22.33)
#   Median: (10.00, 15.00, 20.00)
#   Max Error: 0.50
```

---

## Calculators

### BeCoMeCalculator

Calculator for the BeCoMe (Best Compromise Mean) method.

**Module:** `src.calculators.become_calculator`

#### Class Definition

```python
class BeCoMeCalculator:
    """
    Calculator for the BeCoMe (Best Compromise Mean) method.
    
    The BeCoMe method combines arithmetic mean (Gamma) and statistical median (Omega)
    of expert opinions to produce a best compromise result (GammaOmegaMean).
    """
```

#### Constructor

```python
def __init__(self) -> None
```

No parameters required. The calculator is stateless.

**Example:**

```python
from src.calculators.become_calculator import BeCoMeCalculator

calculator = BeCoMeCalculator()
```

#### Methods

##### `calculate_arithmetic_mean()`

Calculate the arithmetic mean (Γ) of all expert opinions.

```python
def calculate_arithmetic_mean(
    self,
    opinions: list[ExpertOpinion]
) -> FuzzyTriangleNumber
```

**Parameters:**
- `opinions` (list[ExpertOpinion]): List of expert opinions

**Returns:**
- `FuzzyTriangleNumber`: Arithmetic mean Γ(α, γ, β)

**Raises:**
- `ValueError`: If opinions list is empty

**Formula:**
```
α = (1/M) × Σ(Aₖ)  # average of lower bounds
γ = (1/M) × Σ(Cₖ)  # average of peaks
β = (1/M) × Σ(Bₖ)  # average of upper bounds
```

**Example:**

```python
from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

calculator = BeCoMeCalculator()

opinions = [
    ExpertOpinion("Expert 1", FuzzyTriangleNumber(10.0, 15.0, 20.0)),
    ExpertOpinion("Expert 2", FuzzyTriangleNumber(12.0, 18.0, 25.0)),
    ExpertOpinion("Expert 3", FuzzyTriangleNumber(8.0, 14.0, 22.0)),
]

mean = calculator.calculate_arithmetic_mean(opinions)
print(mean)  # (10.00, 15.67, 22.33)
```

##### `calculate_median()`

Calculate the statistical median (Ω) of all expert opinions.

```python
def calculate_median(
    self,
    opinions: list[ExpertOpinion]
) -> FuzzyTriangleNumber
```

**Parameters:**
- `opinions` (list[ExpertOpinion]): List of expert opinions

**Returns:**
- `FuzzyTriangleNumber`: Median Ω(ρ, ω, σ)

**Raises:**
- `ValueError`: If opinions list is empty

**Algorithm:**
1. Sort opinions by centroid values
2. If M is odd: take middle element
3. If M is even: average two middle elements

**Example:**

```python
calculator = BeCoMeCalculator()

opinions = [
    ExpertOpinion("Expert 1", FuzzyTriangleNumber(10.0, 15.0, 20.0)),
    ExpertOpinion("Expert 2", FuzzyTriangleNumber(12.0, 18.0, 25.0)),
    ExpertOpinion("Expert 3", FuzzyTriangleNumber(8.0, 14.0, 22.0)),
]

median = calculator.calculate_median(opinions)
print(median)  # (10.00, 15.00, 20.00) - middle element after sorting
```

##### `calculate_compromise()`

Calculate the best compromise (ΓΩMean) from expert opinions.

```python
def calculate_compromise(
    self,
    opinions: list[ExpertOpinion]
) -> BeCoMeResult
```

**Parameters:**
- `opinions` (list[ExpertOpinion]): List of expert opinions

**Returns:**
- `BeCoMeResult`: Complete result with all intermediate and final values

**Raises:**
- `ValueError`: If opinions list is empty

**Algorithm:**
1. Calculate arithmetic mean (Γ)
2. Calculate statistical median (Ω)
3. Compute best compromise: (Γ + Ω) / 2
4. Calculate maximum error: |Γ - Ω| / 2
5. Return BeCoMeResult with all values

**Example:**

```python
calculator = BeCoMeCalculator()

opinions = [
    ExpertOpinion("Expert 1", FuzzyTriangleNumber(10.0, 15.0, 20.0)),
    ExpertOpinion("Expert 2", FuzzyTriangleNumber(12.0, 18.0, 25.0)),
    ExpertOpinion("Expert 3", FuzzyTriangleNumber(8.0, 14.0, 22.0)),
]

result = calculator.calculate_compromise(opinions)

# Access results
print(f"Best Compromise: {result.best_compromise}")
print(f"Arithmetic Mean: {result.arithmetic_mean}")
print(f"Median: {result.median}")
print(f"Max Error: {result.max_error:.2f}")
print(f"Number of Experts: {result.num_experts}")
print(f"Even number? {result.is_even}")
```

##### `_sort_by_centroid()` (Private)

Sort expert opinions by their centroid values.

```python
def _sort_by_centroid(
    self,
    opinions: list[ExpertOpinion]
) -> list[ExpertOpinion]
```

**Parameters:**
- `opinions` (list[ExpertOpinion]): List of expert opinions

**Returns:**
- `list[ExpertOpinion]`: Sorted list (by ascending centroid)

**Note:** This is a private helper method used internally for median calculation.

---

## Usage Examples

### Basic Usage

```python
from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

# Create calculator
calculator = BeCoMeCalculator()

# Create expert opinions
opinions = [
    ExpertOpinion("Expert 1", FuzzyTriangleNumber(5.0, 10.0, 15.0)),
    ExpertOpinion("Expert 2", FuzzyTriangleNumber(8.0, 12.0, 18.0)),
    ExpertOpinion("Expert 3", FuzzyTriangleNumber(6.0, 11.0, 16.0)),
]

# Calculate best compromise
result = calculator.calculate_compromise(opinions)

# Display results
print(result)
```

### Working with Individual Components

```python
# Calculate only arithmetic mean
mean = calculator.calculate_arithmetic_mean(opinions)
print(f"Arithmetic Mean: {mean}")

# Calculate only median
median = calculator.calculate_median(opinions)
print(f"Median: {median}")

# Access centroid
print(f"Mean Centroid: {mean.get_centroid():.2f}")
```

### Handling Different Numbers of Experts

```python
# Odd number (3 experts)
opinions_odd = [
    ExpertOpinion("E1", FuzzyTriangleNumber(5.0, 10.0, 15.0)),
    ExpertOpinion("E2", FuzzyTriangleNumber(8.0, 12.0, 18.0)),
    ExpertOpinion("E3", FuzzyTriangleNumber(6.0, 11.0, 16.0)),
]

result_odd = calculator.calculate_compromise(opinions_odd)
print(f"Odd - Median takes middle element")
print(f"Is Even: {result_odd.is_even}")  # False

# Even number (4 experts)
opinions_even = opinions_odd + [
    ExpertOpinion("E4", FuzzyTriangleNumber(7.0, 13.0, 19.0))
]

result_even = calculator.calculate_compromise(opinions_even)
print(f"Even - Median averages two middle elements")
print(f"Is Even: {result_even.is_even}")  # True
```

### Error Handling

```python
# Empty list
try:
    result = calculator.calculate_compromise([])
except ValueError as e:
    print(f"Error: {e}")  # "Cannot calculate compromise of empty opinions list"

# Invalid fuzzy number
try:
    invalid_fuzzy = FuzzyTriangleNumber(15.0, 10.0, 5.0)  # Wrong order
except ValueError as e:
    print(f"Error: {e}")  # Constraint violation message
```

### Accessing Result Components

```python
result = calculator.calculate_compromise(opinions)

# Best compromise components
print(f"Lower bound (π): {result.best_compromise.lower_bound:.2f}")
print(f"Peak (φ): {result.best_compromise.peak:.2f}")
print(f"Upper bound (ξ): {result.best_compromise.upper_bound:.2f}")

# Metadata
print(f"Number of experts: {result.num_experts}")
print(f"Precision (Δmax): {result.max_error:.4f}")

# Interpretation
if result.max_error < result.best_compromise.peak * 0.1:
    print("High consensus among experts")
else:
    print("Significant disagreement detected")
```

### Sorting Opinions

```python
# Opinions are automatically sorted in median calculation
unsorted_opinions = [
    ExpertOpinion("E3", FuzzyTriangleNumber(10.0, 15.0, 20.0)),  # Gx = 15.0
    ExpertOpinion("E1", FuzzyTriangleNumber(5.0, 8.0, 12.0)),    # Gx = 8.33
    ExpertOpinion("E2", FuzzyTriangleNumber(8.0, 12.0, 18.0)),   # Gx = 12.67
]

# Sorting happens internally
result = calculator.calculate_compromise(unsorted_opinions)

# Manual sorting (if needed)
sorted_opinions = sorted(unsorted_opinions)
for i, op in enumerate(sorted_opinions, 1):
    print(f"{i}. {op.expert_id}: Gx = {op.get_centroid():.2f}")
```

### Integration with Pydantic

```python
# BeCoMeResult is a Pydantic model
result = calculator.calculate_compromise(opinions)

# Convert to dict
result_dict = result.model_dump()
print(result_dict)

# Convert to JSON
result_json = result.model_dump_json(indent=2)
print(result_json)

# Validate with Pydantic
from pydantic import ValidationError

try:
    invalid_result = BeCoMeResult(
        best_compromise=FuzzyTriangleNumber(10.0, 15.0, 20.0),
        arithmetic_mean=FuzzyTriangleNumber(10.0, 15.0, 20.0),
        median=FuzzyTriangleNumber(10.0, 15.0, 20.0),
        max_error=-1.0,  # Invalid: must be >= 0
        num_experts=3,
        is_even=False
    )
except ValidationError as e:
    print(f"Validation error: {e}")
```

---

## Type Hints

All functions and methods include complete type hints for better IDE support and type checking:

```python
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber
from src.models.become_result import BeCoMeResult

# All types are properly annotated
opinions: list[ExpertOpinion] = [...]
fuzzy: FuzzyTriangleNumber = FuzzyTriangleNumber(5.0, 10.0, 15.0)
result: BeCoMeResult = calculator.calculate_compromise(opinions)
centroid: float = fuzzy.get_centroid()
```

Use `mypy` for static type checking:

```bash
mypy src/
```

---

## Error Reference

### ValueError

**Raised by:** `FuzzyTriangleNumber.__init__`, `BeCoMeCalculator` methods

**Conditions:**
1. Triangular constraint violated: `not (lower_bound <= peak <= upper_bound)`
2. Empty opinions list passed to calculator

**Example:**

```python
# Constraint violation
try:
    FuzzyTriangleNumber(10.0, 5.0, 15.0)  # peak < lower_bound
except ValueError as e:
    print(e)

# Empty list
try:
    calculator.calculate_compromise([])
except ValueError as e:
    print(e)
```

### ValidationError (Pydantic)

**Raised by:** `BeCoMeResult.__init__`

**Conditions:**
1. `max_error < 0`
2. `num_experts < 1`
3. Invalid field types

**Example:**

```python
from pydantic import ValidationError

try:
    BeCoMeResult(
        best_compromise=FuzzyTriangleNumber(10.0, 15.0, 20.0),
        arithmetic_mean=FuzzyTriangleNumber(10.0, 15.0, 20.0),
        median=FuzzyTriangleNumber(10.0, 15.0, 20.0),
        max_error=-0.5,  # Invalid
        num_experts=0,   # Invalid
        is_even=False
    )
except ValidationError as e:
    print(e)
```

---

## Best Practices

### 1. Always Validate Input

```python
def validate_fuzzy_number(a: float, c: float, b: float) -> bool:
    """Check if values form valid fuzzy triangular number."""
    return a <= c <= b

if validate_fuzzy_number(5.0, 10.0, 15.0):
    fuzzy = FuzzyTriangleNumber(5.0, 10.0, 15.0)
```

### 2. Use Meaningful Expert IDs

```python
# Good
opinion = ExpertOpinion("Dr. Smith (Economics)", fuzzy)
opinion = ExpertOpinion("Expert_Finance_01", fuzzy)

# Less helpful
opinion = ExpertOpinion("1", fuzzy)
opinion = ExpertOpinion("x", fuzzy)
```

### 3. Check Precision Indicator

```python
result = calculator.calculate_compromise(opinions)

# Relative error check
relative_error = result.max_error / result.best_compromise.peak

if relative_error < 0.05:
    print("Very high consensus (< 5% error)")
elif relative_error < 0.15:
    print("Acceptable consensus (< 15% error)")
else:
    print("Low consensus - consider collecting more opinions")
```

### 4. Document Units

```python
# Good - units are clear
budget_opinion = ExpertOpinion(
    "CFO",
    FuzzyTriangleNumber(50.0, 75.0, 100.0)  # millions USD
)

# Consider adding metadata
opinion_with_meta = {
    "opinion": ExpertOpinion("CFO", FuzzyTriangleNumber(50.0, 75.0, 100.0)),
    "unit": "millions USD",
    "timestamp": "2025-10-10"
}
```

---

## Performance Considerations

### Time Complexity

| Operation | Complexity | Notes |
|-----------|------------|-------|
| `FuzzyTriangleNumber.get_centroid()` | O(1) | Simple arithmetic |
| `calculate_arithmetic_mean()` | O(M) | M = number of experts |
| `calculate_median()` | O(M log M) | Sorting dominates |
| `calculate_compromise()` | O(M log M) | Median calculation dominates |

### Space Complexity

All operations use O(M) space where M is the number of experts.

### Optimization Tips

```python
# If you only need the final result, use calculate_compromise()
result = calculator.calculate_compromise(opinions)  # Most efficient

# Avoid recalculating if you need multiple values
mean = calculator.calculate_arithmetic_mean(opinions)
median = calculator.calculate_median(opinions)
# Better: use calculate_compromise() once and access result attributes
```

---

## Related Documentation

- **Method Description**: `docs/method-description.md` - Mathematical foundation
- **UML Diagrams**: `docs/uml-diagrams.md` - Visual architecture
- **Examples**: `examples/` - Real-world case studies
- **README**: `README.md` - Quick start guide

---

*Last updated: 2025-10-10*  
*Generated from source code with full type annotations*

