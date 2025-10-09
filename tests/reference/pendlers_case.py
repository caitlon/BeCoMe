"""
Pendlers (cross-border travel) case study from Excel reference implementation.

This case study contains data from the "CASE STUDY - PENDLERS" sheet
with 22 experts providing Likert scale ratings (0-25-50-75-100).
"""

from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

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
