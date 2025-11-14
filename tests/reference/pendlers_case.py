"""Pendlers (cross-border travel) case study from Excel reference implementation.

This case study contains data from the "CASE STUDY - PENDLERS" sheet
with 22 experts providing Likert scale ratings (0-25-50-75-100).

Expert opinions are loaded from examples/data/pendlers_case.txt to avoid duplication.
Only expected results from Excel calculations are stored here for verification.

Special characteristics:
    Likert scale data represents crisp values (lower_bound = peak = upper_bound)
    This differs from interval estimates in Budget and Floods cases

Mathematical notation for BeCoMe fuzzy number calculations:

Best compromise fuzzy number (π, φ, ψ):
    π = (α + ρ)/2  - lower bound
    φ = (γ + ω)/2  - peak
    ψ = (β + σ)/2  - upper bound

Arithmetic mean fuzzy number (α, γ, β):
    α - average of all expert lower bounds
    γ - average of all expert peaks
    β - average of all expert upper bounds

Median fuzzy number (ρ, ω, σ):
    ρ - median of all expert lower bounds
    ω - median of all expert peaks
    σ - median of all expert upper bounds

Error metric:
    max_error = |mean_centroid - median_centroid|/2

For detailed explanation see BeCoMe algorithm documentation.
"""
# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF002

from tests.reference._case_factory import create_case

PENDLERS_CASE = create_case(
    case_name="Pendlers",
    expected_result={
        "best_compromise_peak": 30.68181818,
        "max_error": 5.68181818,
        "num_experts": 22,
        "median_peak": 25.0,
        "median_lower": 25.0,
        "median_upper": 25.0,
        "mean_peak": 36.36363636,
    },
)
