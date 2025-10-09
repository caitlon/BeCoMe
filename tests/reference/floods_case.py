"""
Floods case study from Excel reference implementation.

This case study contains data from the "CASE STUDY 3 - FLOODS" sheet
with 13 experts providing interval estimates for flood prevention measures.
"""
# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF003

from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

FLOODS_CASE = {
    # Expert opinions data
    "opinions": [
        ExpertOpinion(
            "Hydrologist 1", FuzzyTriangleNumber(lower_bound=37, peak=42, upper_bound=47)
        ),
        ExpertOpinion(
            "Hydrologist 2", FuzzyTriangleNumber(lower_bound=42, peak=50, upper_bound=50)
        ),
        ExpertOpinion(
            "Nature protection", FuzzyTriangleNumber(lower_bound=5, peak=7, upper_bound=9)
        ),
        ExpertOpinion(
            "Risk management", FuzzyTriangleNumber(lower_bound=37, peak=40, upper_bound=48)
        ),
        ExpertOpinion("Land use", FuzzyTriangleNumber(lower_bound=6, peak=8, upper_bound=11)),
        ExpertOpinion("Civil service", FuzzyTriangleNumber(lower_bound=5, peak=8, upper_bound=9)),
        ExpertOpinion(
            "Municipality 1", FuzzyTriangleNumber(lower_bound=33, peak=38, upper_bound=43)
        ),
        ExpertOpinion("Municipality 2", FuzzyTriangleNumber(lower_bound=5, peak=8, upper_bound=8)),
        ExpertOpinion("Economist", FuzzyTriangleNumber(lower_bound=10, peak=14, upper_bound=20)),
        ExpertOpinion(
            "Rescue coordinator", FuzzyTriangleNumber(lower_bound=40, peak=45, upper_bound=50)
        ),
        ExpertOpinion("Land owner 1", FuzzyTriangleNumber(lower_bound=2, peak=3, upper_bound=4)),
        ExpertOpinion("Land owner 2", FuzzyTriangleNumber(lower_bound=0, peak=0, upper_bound=2)),
        ExpertOpinion("Land owner 3", FuzzyTriangleNumber(lower_bound=0, peak=2, upper_bound=3)),
    ],
    # Expected results from Excel
    "expected_result": {
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
    # Description for documentation and examples
    "description": """
    Case Study - Floods:
    Real case study about flood prevention. Experts have expressed their standpoint
    as a numerical interval or a number regarding the question:
    "What percentage reduction of arable land in flood areas is recommended
    to prevent floods?"

    This case demonstrates BeCoMe with 13 experts (odd number) where opinions
    are highly polarized between land owners (low percentages) and hydrologists/
    rescue services (high percentages).
    """,
}
