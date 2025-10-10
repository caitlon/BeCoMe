# BeCoMe Method Description

## Overview

BeCoMe (Best Compromise Mean) is a method for aggregating expert opinions expressed as fuzzy triangular numbers. The method was developed by I. Vrana, J. Tyrychtr, and M. Pelikan at the Czech University of Life Sciences Prague.

## Mathematical Foundation

### Fuzzy Triangular Numbers

A fuzzy triangular number is defined by three values:
- **A** (lower_bound) - minimum value
- **C** (peak) - most likely value
- **B** (upper_bound) - maximum value

Where: A ≤ C ≤ B

### Centroid Calculation

The centroid (center of gravity) of a fuzzy triangular number is calculated as:

```
Gx = (A + C + B) / 3
```

### BeCoMe Algorithm

The BeCoMe method calculates the best compromise from M expert opinions through the following steps:

1. **Calculate Arithmetic Mean (Γ)**
   - For each component (lower, peak, upper), calculate the arithmetic mean across all experts
   - Results in a fuzzy triangular number Γ(α, γ, β)

2. **Calculate Median (Ω)**
   - Sort all expert opinions by their centroid values
   - Find the median fuzzy number Ω(ρ, ω, σ)
   - For odd M: take the middle element
   - For even M: average the two middle elements

3. **Calculate Final Compromise (ΓΩMean)**
   - The best compromise is the average of the arithmetic mean and median:
   ```
   ΓΩMean = (Γ + Ω) / 2
   ```

4. **Calculate Precision Indicator (Δmax)**
   - Maximum error is calculated as:
   ```
   Δmax = |Γ - Ω| / 2
   ```

## Key Advantages

- Combines both mean and median for robust aggregation
- Resistant to outliers through median calculation
- Provides precision indicator for decision confidence
- Mathematically sound and interpretable

## References

Vrana, I., Tyrychtr, J., & Pelikan, M. (2021). BeCoMe – A new approach for fuzzy group decision making. Expert Systems with Applications.


