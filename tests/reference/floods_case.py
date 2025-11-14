"""Floods case study from Excel reference implementation.

This case study contains data from the "CASE STUDY 3 - FLOODS" sheet
with 13 experts providing interval estimates for flood prevention measures.

Expert opinions are loaded from examples/data/floods_case.txt to avoid duplication.
Only expected results from Excel calculations are stored here for verification.

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
    For odd number of experts (13): middle expert's values
    ρ - median of all expert lower bounds
    ω - median of all expert peaks
    σ - median of all expert upper bounds

Error metric:
    max_error = |mean_centroid - median_centroid|/2

For detailed explanation see BeCoMe algorithm documentation.
"""
# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF003

from tests.reference._case_factory import create_case

FLOODS_CASE = create_case(
    case_name="Floods",
    expected_result={
        "best_compromise_lower": 11.538461538461538,
        "best_compromise_peak": 14.192307692307692,
        "best_compromise_upper": 17.192307692307693,
        "best_compromise_centroid": 14.307692307692307,
        "mean_lower": 17.076923076923077,
        "mean_peak": 20.384615384615383,
        "mean_upper": 23.384615384615383,
        "mean_centroid": 20.28205128205128,
        "median_lower": 6.0,
        "median_peak": 8.0,
        "median_upper": 11.0,
        "median_of_centroids": 8.333333333333334,
        "max_error": 5.974358974358974,
        "num_experts": 13,
    },
)
