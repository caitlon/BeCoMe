"""
Floods case study from Excel reference implementation.

This case study contains data from the "CASE STUDY 3 - FLOODS" sheet
with 13 experts providing interval estimates for flood prevention measures.

IMPORTANT: Expert opinions are loaded from examples/data/floods_case.txt
to avoid duplication. This file is the single source of truth for opinion data.
Only expected results are stored here as they are unique to testing.
"""
# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF003

from tests.reference._case_factory import create_case

FLOODS_CASE = create_case(
    case_name="Floods",
    expected_result={
        # Best compromise fuzzy number: (π, φ, ψ) = (lower, peak, upper)
        "best_compromise_lower": 11.538461538461538,  # π = (α + ρ)/2
        "best_compromise_peak": 14.192307692307692,  # φ = (γ + ω)/2
        "best_compromise_upper": 17.192307692307693,  # ψ = (β + σ)/2
        "best_compromise_centroid": 14.307692307692307,  # (π + φ + ψ)/3 - shown in Excel
        # Arithmetic mean fuzzy number: (α, γ, β)
        "mean_lower": 17.076923076923077,  # α - average of lower bounds
        "mean_peak": 20.384615384615383,  # γ - average of peaks
        "mean_upper": 23.384615384615383,  # β - average of upper bounds
        "mean_centroid": 20.28205128205128,  # (α + γ + β)/3 - "Průměr celkem" in Excel
        # Median fuzzy number: (ρ, ω, σ) - middle expert for odd number
        "median_lower": 6.0,  # ρ - lower bound of median expert
        "median_peak": 8.0,  # ω - peak of median expert
        "median_upper": 11.0,  # σ - upper bound of median expert
        "median_of_centroids": 8.333333333333334,  # Median of all Gx values
        # Error metrics
        "max_error": 5.974358974358974,  # |mean_centroid - median_centroid|/2
        "num_experts": 13,
    },
)
