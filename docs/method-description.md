# BeCoMe Method Description

## Overview

**BeCoMe** (Best Compromise Mean) is a method for aggregating expert opinions expressed as fuzzy triangular numbers. The method was developed by I. Vrana, J. Tyrychtr, and M. Pelikan at the Czech University of Life Sciences Prague.

BeCoMe combines two classical aggregation approaches:
- **Arithmetic mean (Γ)** - represents the average opinion
- **Statistical median (Ω)** - represents the central tendency, resistant to outliers

The final result is the **best compromise (ΓΩMean)** - the average of these two measures, providing a robust consensus estimate.

---

## Mathematical Foundation

### 1. Fuzzy Triangular Numbers

A **fuzzy triangular number** is a special type of fuzzy set that represents uncertain or imprecise information. It is defined by three characteristic values:

- **A** (`lower_bound`) - minimum possible value
- **C** (`peak`) - most likely value (mode)
- **B** (`upper_bound`) - maximum possible value

**Constraint:** `A ≤ C ≤ B`

#### Visual Representation

```
  Membership
  μ(x)
    1 |        /\
      |       /  \
      |      /    \
      |     /      \
    0 |____/________\____
         A    C    B      x
```

The triangular shape represents the membership function:
- At point **C** (peak), membership = 1 (fully certain)
- At points **A** and **B**, membership = 0 (boundary values)
- Between A-C and C-B, membership decreases linearly

#### Notation

A fuzzy triangular number is denoted as: **FTN(A, C, B)** or **(A, C, B)**

#### Example

An expert estimates project duration:
- Optimistic: 5 days (minimum)
- Most likely: 8 days (peak)
- Pessimistic: 12 days (maximum)

This is represented as: **FTN(5, 8, 12)**

---

### 2. Centroid Calculation

The **centroid** (center of gravity) is the x-coordinate of the center of mass of the triangular fuzzy number.

**Formula:**
```
Gx = (A + C + B) / 3
```

**Geometric interpretation:** The centroid represents the "balance point" of the triangle.

**Purpose:** Used for sorting expert opinions in median calculation.

#### Example

For FTN(5, 8, 12):
```
Gx = (5 + 8 + 12) / 3 = 25 / 3 ≈ 8.33
```

---

## BeCoMe Algorithm - Step by Step

The BeCoMe method aggregates **M** expert opinions into a single best compromise result through five steps.

### Input

A set of **M** expert opinions, each represented as a fuzzy triangular number:
```
E₁ = (A₁, C₁, B₁)
E₂ = (A₂, C₂, B₂)
...
Eₘ = (Aₘ, Cₘ, Bₘ)
```

---

### Step 1: Calculate Arithmetic Mean (Γ)

The arithmetic mean **Γ(α, γ, β)** is calculated by averaging each component separately.

**Formulas:**
```
α = (1/M) × Σ(Aₖ)  for k = 1 to M   (average of lower bounds)
γ = (1/M) × Σ(Cₖ)  for k = 1 to M   (average of peaks)
β = (1/M) × Σ(Bₖ)  for k = 1 to M   (average of upper bounds)
```

**Result:** Γ = (α, γ, β)

#### Example (3 experts)

Three experts estimate project cost (in thousands):
```
Expert 1: E₁ = (10, 15, 20)
Expert 2: E₂ = (12, 18, 25)
Expert 3: E₃ = (8,  14, 22)
```

**Calculation:**
```
α = (10 + 12 + 8) / 3 = 30 / 3 = 10.00
γ = (15 + 18 + 14) / 3 = 47 / 3 ≈ 15.67
β = (20 + 25 + 22) / 3 = 67 / 3 ≈ 22.33
```

**Result:** Γ = (10.00, 15.67, 22.33)

---

### Step 2: Calculate Median (Ω)

The median **Ω(ρ, ω, σ)** is found by sorting opinions by their centroids and taking the middle value(s).

#### Step 2.1: Calculate Centroids

For each expert opinion, calculate the centroid:
```
Gxₖ = (Aₖ + Cₖ + Bₖ) / 3
```

#### Step 2.2: Sort by Centroid

Sort all expert opinions in ascending order by their centroid values.

#### Step 2.3: Find Median

**Case A: Odd number of experts (M = 2n + 1)**

Take the middle element at position **n + 1**:
```
Ω = E_{middle}
ρ = A_{middle}
ω = C_{middle}
σ = B_{middle}
```

**Case B: Even number of experts (M = 2n)**

Average the two middle elements at positions **n** and **n + 1**:
```
ρ = (A_n + A_{n+1}) / 2
ω = (C_n + C_{n+1}) / 2
σ = (B_n + B_{n+1}) / 2
```

**Result:** Ω = (ρ, ω, σ)

#### Example (3 experts - odd)

Using the same data from Step 1:
```
Expert 1: E₁ = (10, 15, 20) → Gx₁ = 45/3 = 15.00
Expert 2: E₂ = (12, 18, 25) → Gx₂ = 55/3 ≈ 18.33
Expert 3: E₃ = (8,  14, 22) → Gx₃ = 44/3 ≈ 14.67
```

**Sorted by centroid:**
```
1. Expert 3: (8,  14, 22) → Gx = 14.67
2. Expert 1: (10, 15, 20) → Gx = 15.00  ← Middle element (n=1, position 2)
3. Expert 2: (12, 18, 25) → Gx = 18.33
```

**Result:** Ω = (10, 15, 20) (the middle element)

#### Example (4 experts - even)

Adding a fourth expert:
```
Expert 4: E₄ = (11, 16, 23) → Gx₄ = 50/3 ≈ 16.67
```

**Sorted by centroid:**
```
1. Expert 3: (8,  14, 22) → Gx = 14.67
2. Expert 1: (10, 15, 20) → Gx = 15.00  ← Position n (2)
3. Expert 4: (11, 16, 23) → Gx = 16.67  ← Position n+1 (3)
4. Expert 2: (12, 18, 25) → Gx = 18.33
```

**Calculation:**
```
ρ = (10 + 11) / 2 = 10.5
ω = (15 + 16) / 2 = 15.5
σ = (20 + 23) / 2 = 21.5
```

**Result:** Ω = (10.5, 15.5, 21.5)

---

### Step 3: Calculate Best Compromise (ΓΩMean)

The best compromise **ΓΩMean(π, φ, ξ)** is the average of the arithmetic mean and median.

**Formulas:**
```
π = (α + ρ) / 2   (average of lower bounds)
φ = (γ + ω) / 2   (average of peaks)
ξ = (β + σ) / 2   (average of upper bounds)
```

**Result:** ΓΩMean = (π, φ, ξ)

#### Example (3 experts)

Using results from Steps 1 and 2:
```
Γ = (10.00, 15.67, 22.33)
Ω = (10.00, 15.00, 20.00)
```

**Calculation:**
```
π = (10.00 + 10.00) / 2 = 10.00
φ = (15.67 + 15.00) / 2 = 15.33
ξ = (22.33 + 20.00) / 2 = 21.17
```

**Result:** ΓΩMean = (10.00, 15.33, 21.17)

---

### Step 4: Calculate Maximum Error (Δmax)

The **maximum error Δmax** is a precision indicator that measures the distance between the arithmetic mean and median.

**Formula:**
```
Δmax = |centroid(Γ) - centroid(Ω)| / 2
```

**Expanded:**
```
Δmax = |Gx(Γ) - Gx(Ω)| / 2
     = |(α + γ + β)/3 - (ρ + ω + σ)/3| / 2
```

**Interpretation:**
- **Lower Δmax** → Higher agreement among experts
- **Higher Δmax** → Greater disagreement or presence of outliers

#### Example (3 experts)

Using results from previous steps:
```
Γ = (10.00, 15.67, 22.33)
Ω = (10.00, 15.00, 20.00)
```

**Calculation:**
```
Gx(Γ) = (10.00 + 15.67 + 22.33) / 3 = 48.00 / 3 = 16.00
Gx(Ω) = (10.00 + 15.00 + 20.00) / 3 = 45.00 / 3 = 15.00

Δmax = |16.00 - 15.00| / 2 = 1.00 / 2 = 0.50
```

**Result:** Δmax = 0.50

---

### Step 5: Summary of Results

The complete BeCoMe result includes:

| Component | Value | Description |
|-----------|-------|-------------|
| **Best Compromise (ΓΩMean)** | (10.00, 15.33, 21.17) | Final aggregated opinion |
| **Arithmetic Mean (Γ)** | (10.00, 15.67, 22.33) | Average of all opinions |
| **Median (Ω)** | (10.00, 15.00, 20.00) | Central tendency |
| **Maximum Error (Δmax)** | 0.50 | Precision indicator |
| **Number of Experts (M)** | 3 | Count of opinions |
| **Is Even?** | False | Affects median calculation |

---

## Complete Worked Example

### Scenario: Project Budget Estimation

Five project managers estimate the required budget (in millions):

```
Manager 1: (5.0, 8.0, 12.0)
Manager 2: (6.0, 9.0, 14.0)
Manager 3: (4.0, 7.0, 11.0)
Manager 4: (7.0, 10.0, 15.0)
Manager 5: (5.5, 8.5, 13.0)
```

### Solution

**Step 1: Arithmetic Mean**
```
α = (5.0 + 6.0 + 4.0 + 7.0 + 5.5) / 5 = 27.5 / 5 = 5.50
γ = (8.0 + 9.0 + 7.0 + 10.0 + 8.5) / 5 = 42.5 / 5 = 8.50
β = (12.0 + 14.0 + 11.0 + 15.0 + 13.0) / 5 = 65.0 / 5 = 13.00

Γ = (5.50, 8.50, 13.00)
```

**Step 2: Median (M = 5, odd)**

Calculate centroids:
```
Manager 1: Gx = (5.0 + 8.0 + 12.0) / 3 = 8.33
Manager 2: Gx = (6.0 + 9.0 + 14.0) / 3 = 9.67
Manager 3: Gx = (4.0 + 7.0 + 11.0) / 3 = 7.33
Manager 4: Gx = (7.0 + 10.0 + 15.0) / 3 = 10.67
Manager 5: Gx = (5.5 + 8.5 + 13.0) / 3 = 9.00
```

Sort by centroid:
```
1. Manager 3: (4.0, 7.0, 11.0)  → Gx = 7.33
2. Manager 1: (5.0, 8.0, 12.0)  → Gx = 8.33
3. Manager 5: (5.5, 8.5, 13.0)  → Gx = 9.00  ← Middle (position 3)
4. Manager 2: (6.0, 9.0, 14.0)  → Gx = 9.67
5. Manager 4: (7.0, 10.0, 15.0) → Gx = 10.67
```

Middle element (position 3):
```
Ω = (5.5, 8.5, 13.0)
```

**Step 3: Best Compromise**
```
π = (5.50 + 5.5) / 2 = 5.50
φ = (8.50 + 8.5) / 2 = 8.50
ξ = (13.00 + 13.0) / 2 = 13.00

ΓΩMean = (5.50, 8.50, 13.00)
```

**Step 4: Maximum Error**
```
Gx(Γ) = (5.50 + 8.50 + 13.00) / 3 = 9.00
Gx(Ω) = (5.5 + 8.5 + 13.0) / 3 = 9.00

Δmax = |9.00 - 9.00| / 2 = 0.00
```

**Interpretation:** Δmax = 0 means perfect agreement (arithmetic mean equals median).

---

## Key Properties of BeCoMe

### 1. Robustness

**Combination of mean and median provides:**
- Sensitivity to all data (via arithmetic mean)
- Resistance to outliers (via median)
- Balanced compromise between both approaches

### 2. Mathematical Soundness

**Properties preserved:**
- If all experts agree, BeCoMe returns the consensus value
- Result always satisfies triangular constraint: π ≤ φ ≤ ξ
- Commutative: order of experts doesn't affect the result (except for numerical precision)

### 3. Interpretability

**All components have clear meaning:**
- **Γ** - what experts say on average
- **Ω** - what the central expert says
- **ΓΩMean** - balanced compromise
- **Δmax** - level of disagreement

### 4. Precision Indicator

**Δmax provides decision confidence:**
```
Δmax ≈ 0     → High consensus, confident decision
Δmax << φ    → Acceptable agreement
Δmax ≥ φ     → Low consensus, need more discussion
```

---

## Comparison with Classical Methods

| Method | Strengths | Weaknesses |
|--------|-----------|------------|
| **Arithmetic Mean only** | Simple, uses all data | Sensitive to outliers |
| **Median only** | Robust to outliers | Ignores non-central opinions |
| **BeCoMe** | Combines both advantages | Slightly more complex |

---

## When to Use BeCoMe

### Ideal Scenarios

1. **Expert panel decision-making** - multiple experts provide estimates
2. **Uncertain information** - precise values unknown, ranges given
3. **Risk assessment** - optimistic, realistic, pessimistic scenarios
4. **Budget estimation** - min, most likely, max costs
5. **Time estimation** - project duration with uncertainty

### Requirements

- At least 1 expert opinion (though 3+ recommended)
- Opinions expressible as triangular fuzzy numbers
- Need for robust aggregation resistant to outliers

---

## Advantages

✓ **Mathematically sound** - based on established statistical principles  
✓ **Robust** - resistant to outliers through median component  
✓ **Interpretable** - all results have clear meaning  
✓ **Flexible** - works with any number of experts (odd or even)  
✓ **Provides confidence** - Δmax indicates level of agreement  
✓ **Preserves uncertainty** - maintains fuzzy nature of input  

---

## Limitations

- Assumes opinions can be represented as triangular fuzzy numbers
- Requires expert judgment to convert verbal assessments to fuzzy numbers
- More complex than simple averaging (but worth the added robustness)
- Centroid-based sorting may group opinions differently than peak-based sorting

---

## Implementation Notes

This Python implementation follows the original algorithm exactly:

- Component-wise operations on fuzzy triangular numbers
- Centroid-based sorting for median calculation
- Separate handling for odd/even number of experts
- Validation of triangular constraint (A ≤ C ≤ B)

For code examples and usage, see:
- `README.md` - Quick start guide
- `examples/` - Real-world case studies
- `docs/api-reference.md` - Complete API documentation

---

## References

**Primary source:**
> Vrana, I., Tyrychtr, J., & Pelikan, M. (2021). BeCoMe – A new approach for fuzzy group decision making. *Expert Systems with Applications*, Volume 177, Article 114936.

**Related topics:**
- Fuzzy set theory (Zadeh, 1965)
- Fuzzy numbers and arithmetic
- Group decision-making under uncertainty
- Aggregation operators

---

## Further Reading

- **Fuzzy Set Theory**: Zadeh, L.A. (1965). "Fuzzy sets". *Information and Control*, 8(3), 338-353.
- **Fuzzy Numbers**: Dubois, D., & Prade, H. (1978). "Operations on fuzzy numbers". *International Journal of Systems Science*, 9(6), 613-626.
- **Group Decision Making**: Kacprzyk, J., & Fedrizzi, M. (1988). "A 'soft' measure of consensus in the setting of partial (fuzzy) preferences". *European Journal of Operational Research*, 34(3), 316-325.

---

*Last updated: 2025-10-10*  
*Based on original BeCoMe paper by Vrana et al. (2021)*
