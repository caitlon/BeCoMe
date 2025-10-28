"""
Budget case study from Excel reference implementation.

This case study contains data from the "CASE STUDY - BUDGET" sheet
with 22 experts providing interval estimates for COVID-19 pandemic budget support.

IMPORTANT: Expert opinions are loaded from examples/data/budget_case.txt
to avoid duplication. This file is the single source of truth for opinion data.
Only expected results are stored here as they are unique to testing.
"""
# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF003

from pathlib import Path

from examples.utils import load_data_from_txt

# Load opinions from txt file (single source of truth)
_txt_file = Path(__file__).parent.parent.parent / "examples" / "data" / "budget_case.txt"
_opinions, _metadata = load_data_from_txt(str(_txt_file))

BUDGET_CASE = {
    # Expert opinions data loaded from txt file
    "opinions": _opinions,
    # Expected results from Excel
    "expected_result": {
        # Best compromise fuzzy number: (π, φ, ψ) = (lower, peak, upper)
        "best_compromise_lower": 33.52272727272727,  # π = (α + ρ)/2
        "best_compromise_peak": 51.25,  # φ = (γ + ω)/2
        "best_compromise_upper": 59.31818181818182,  # ψ = (β + σ)/2
        "best_compromise_centroid": 48.03,  # (π + φ + ψ)/3 - shown as result in Excel
        # Arithmetic mean fuzzy number: (α, γ, β)
        "mean_lower": 32.04545454545455,  # α - average of lower bounds
        "mean_peak": 52.5,  # γ - average of peaks
        "mean_upper": 66.13636363636364,  # β - average of upper bounds
        "mean_centroid": 50.23,  # (α + γ + β)/3 - "Průměr celkem" in Excel
        # Median fuzzy number: (ρ, ω, σ) - average of 11th and 12th experts
        "median_lower": 35.0,  # ρ = (30 + 40)/2
        "median_peak": 50.0,  # ω = (50 + 50)/2
        "median_upper": 52.5,  # σ = (55 + 50)/2
        "median_of_centroids": 45.83,  # Median of all Gx values
        # Error metrics
        "max_error": 2.20,  # |mean_centroid - median_centroid|/2
        "num_experts": 22,
    },
    # Description from txt file metadata
    "description": _metadata.get("description", "Budget case study"),
}
