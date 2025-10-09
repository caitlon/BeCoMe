"""
Reference data from Excel examples for testing and validation.

This file contains pre-defined test cases from the BeCoMe Excel reference file
(supplementary/DP-EN-BECOME-FuzzyDecisionTool.xlsx) for testing and validation.
"""
# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF003

from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

# Case study from Excel: Budget case with 22 experts
# Based on the "CASE STUDY - BUDGET" sheet
BUDGET_CASE = {
    # Expert opinions data
    "opinions": [
        ExpertOpinion("Chairman", FuzzyTriangleNumber(lower_bound=40, peak=70, upper_bound=90)),
        ExpertOpinion(
            "Deputy chairman", FuzzyTriangleNumber(lower_bound=60, peak=80, upper_bound=90)
        ),
        ExpertOpinion(
            "Deputy Minister of MI", FuzzyTriangleNumber(lower_bound=60, peak=90, upper_bound=90)
        ),
        ExpertOpinion(
            "Deputy Minister of MD", FuzzyTriangleNumber(lower_bound=30, peak=40, upper_bound=40)
        ),
        ExpertOpinion(
            "Deputy Minister of MFA", FuzzyTriangleNumber(lower_bound=40, peak=70, upper_bound=90)
        ),
        ExpertOpinion(
            "Deputy Minister of MF", FuzzyTriangleNumber(lower_bound=30, peak=45, upper_bound=70)
        ),
        ExpertOpinion(
            "Deputy Minister of MH", FuzzyTriangleNumber(lower_bound=40, peak=60, upper_bound=85)
        ),
        ExpertOpinion(
            "Deputy Minister of MIT", FuzzyTriangleNumber(lower_bound=40, peak=90, upper_bound=90)
        ),
        ExpertOpinion(
            "Deputy Minister of MT", FuzzyTriangleNumber(lower_bound=40, peak=50, upper_bound=50)
        ),
        ExpertOpinion(
            "Deputy Minister of MEYS", FuzzyTriangleNumber(lower_bound=15, peak=40, upper_bound=60)
        ),
        ExpertOpinion(
            "Deputy Minister of MA", FuzzyTriangleNumber(lower_bound=40, peak=50, upper_bound=70)
        ),
        ExpertOpinion(
            "Deputy Minister of MoLSA", FuzzyTriangleNumber(lower_bound=10, peak=50, upper_bound=50)
        ),
        ExpertOpinion(
            "Deputy Minister of MC", FuzzyTriangleNumber(lower_bound=10, peak=30, upper_bound=40)
        ),
        ExpertOpinion(
            "Deputy Minister of MJ", FuzzyTriangleNumber(lower_bound=10, peak=40, upper_bound=50)
        ),
        ExpertOpinion(
            "Chairman of the SSHR", FuzzyTriangleNumber(lower_bound=40, peak=40, upper_bound=40)
        ),
        ExpertOpinion(
            "Police President", FuzzyTriangleNumber(lower_bound=50, peak=50, upper_bound=50)
        ),
        ExpertOpinion(
            "Director of Fire Rescue Service",
            FuzzyTriangleNumber(lower_bound=30, peak=40, upper_bound=50),
        ),
        ExpertOpinion(
            "Chief of General Staff of the ACR",
            FuzzyTriangleNumber(lower_bound=10, peak=40, upper_bound=45),
        ),
        ExpertOpinion(
            "Director of NÚKIB", FuzzyTriangleNumber(lower_bound=10, peak=40, upper_bound=80)
        ),
        ExpertOpinion(
            "Chief hygienist", FuzzyTriangleNumber(lower_bound=10, peak=30, upper_bound=80)
        ),
        ExpertOpinion(
            "Director of SZÚ", FuzzyTriangleNumber(lower_bound=30, peak=50, upper_bound=55)
        ),
        ExpertOpinion(
            "Director of the Office of the Government",
            FuzzyTriangleNumber(lower_bound=60, peak=60, upper_bound=90),
        ),
    ],
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
    # Description for documentation and examples
    "description": """
    Case Study - Budget:
    Experts have expressed their standpoint as a numerical interval or a number
    regarding the state budget of the Czech Republic and the total financial
    support in the range CZK 0-100 billion for entrepreneurs affected by the COVID-19 pandemic.
    """,
}

# Case study from Excel: Cross-border travel (Pendlers) case with 22 experts
# Based on the "CASE STUDY - PENDLERS" sheet with Likert scale
PENDLERS_CASE = {
    # Expert opinions data - For Likert scale, we create triangular numbers
    # where all three values are the same (crisp values)
    "opinions": [
        ExpertOpinion("Chairman", FuzzyTriangleNumber(lower_bound=75, peak=75, upper_bound=75)),
        ExpertOpinion(
            "Deputy chairman", FuzzyTriangleNumber(lower_bound=25, peak=25, upper_bound=25)
        ),
        ExpertOpinion(
            "Deputy Minister of MI", FuzzyTriangleNumber(lower_bound=0, peak=0, upper_bound=0)
        ),
        ExpertOpinion(
            "Deputy Minister of MD", FuzzyTriangleNumber(lower_bound=0, peak=0, upper_bound=0)
        ),
        ExpertOpinion(
            "Deputy Minister of MFA",
            FuzzyTriangleNumber(lower_bound=100, peak=100, upper_bound=100),
        ),
        ExpertOpinion(
            "Deputy Minister of MF", FuzzyTriangleNumber(lower_bound=50, peak=50, upper_bound=50)
        ),
        ExpertOpinion(
            "Deputy Minister of MH", FuzzyTriangleNumber(lower_bound=25, peak=25, upper_bound=25)
        ),
        ExpertOpinion(
            "Deputy Minister of MIT", FuzzyTriangleNumber(lower_bound=75, peak=75, upper_bound=75)
        ),
        ExpertOpinion(
            "Deputy Minister of MT", FuzzyTriangleNumber(lower_bound=25, peak=25, upper_bound=25)
        ),
        ExpertOpinion(
            "Deputy Minister of MEYS", FuzzyTriangleNumber(lower_bound=25, peak=25, upper_bound=25)
        ),
        ExpertOpinion(
            "Deputy Minister of MA", FuzzyTriangleNumber(lower_bound=0, peak=0, upper_bound=0)
        ),
        ExpertOpinion(
            "Deputy Minister of MoLSA", FuzzyTriangleNumber(lower_bound=75, peak=75, upper_bound=75)
        ),
        ExpertOpinion(
            "Deputy Minister of MC", FuzzyTriangleNumber(lower_bound=50, peak=50, upper_bound=50)
        ),
        ExpertOpinion(
            "Deputy Minister of MJ", FuzzyTriangleNumber(lower_bound=75, peak=75, upper_bound=75)
        ),
        ExpertOpinion(
            "Chairman of the SSHR", FuzzyTriangleNumber(lower_bound=25, peak=25, upper_bound=25)
        ),
        ExpertOpinion(
            "Police President", FuzzyTriangleNumber(lower_bound=50, peak=50, upper_bound=50)
        ),
        ExpertOpinion(
            "Director of Fire Rescue Service",
            FuzzyTriangleNumber(lower_bound=25, peak=25, upper_bound=25),
        ),
        ExpertOpinion(
            "Chief of General Staff of the ACR",
            FuzzyTriangleNumber(lower_bound=25, peak=25, upper_bound=25),
        ),
        ExpertOpinion(
            "Director of NÚKIB", FuzzyTriangleNumber(lower_bound=25, peak=25, upper_bound=25)
        ),
        ExpertOpinion("Chief hygienist", FuzzyTriangleNumber(lower_bound=0, peak=0, upper_bound=0)),
        ExpertOpinion(
            "Director of SZU", FuzzyTriangleNumber(lower_bound=25, peak=25, upper_bound=25)
        ),
        ExpertOpinion(
            "Director of the Office of the Government",
            FuzzyTriangleNumber(lower_bound=25, peak=25, upper_bound=25),
        ),
    ],
    # Expected results from Excel
    "expected_result": {
        "best_compromise_peak": 30.68181818,  # From screenshot (exact value)
        "max_error": 5.68181818,
        "num_experts": 22,
        # Values visible in the second screenshot
        "median_peak": 25.0,  # From "Median" value
        "median_lower": 25.0,  # Lower bound of median
        "median_upper": 25.0,  # Upper bound of median
        "mean_peak": 36.36363636,  # From the phi value shown in Excel
    },
    # Description for documentation and examples
    "description": """
    Case Study - Pendlers:
    Experts have expressed their standpoint in LIKERT scale (0-25-50-75-100)
    regarding the statement: "I agree that cross-border travel should be allowed
    for those who regularly travel from one country to another to work."

    Likert scale values:
    0 = Strongly disagree
    25 = Rather disagree
    50 = Neutral
    75 = Rather agree
    100 = Strongly agree

    The closest Likert value to the result is "Rather disagree" (25).
    The decision is NOT AGREED.
    """,
}

# Additional cases can be added as needed
# CASE_3 = { ... }
