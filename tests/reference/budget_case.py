"""Budget case study from Excel reference implementation.

This case study contains data from the "CASE STUDY - BUDGET" sheet
with 22 experts providing interval estimates for COVID-19 pandemic budget support.

Expert opinions are loaded from examples/data/budget_case.txt to avoid duplication.
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

BUDGET_CASE = create_case(
    case_name="Budget",
    expected_result={
        "best_compromise_lower": 33.52272727272727,
        "best_compromise_peak": 51.25,
        "best_compromise_upper": 59.31818181818182,
        "best_compromise_centroid": 48.03,
        "mean_lower": 32.04545454545455,
        "mean_peak": 52.5,
        "mean_upper": 66.13636363636364,
        "mean_centroid": 50.23,
        "median_lower": 35.0,
        "median_peak": 50.0,
        "median_upper": 52.5,
        "median_of_centroids": 45.83,
        "max_error": 2.20,
        "num_experts": 22,
    },
)
