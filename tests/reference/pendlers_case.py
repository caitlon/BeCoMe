"""
Pendlers (cross-border travel) case study from Excel reference implementation.

This case study contains data from the "CASE STUDY - PENDLERS" sheet
with 22 experts providing Likert scale ratings (0-25-50-75-100).

IMPORTANT: Expert opinions are loaded from examples/data/pendlers_case.txt
to avoid duplication. This file is the single source of truth for opinion data.
Only expected results are stored here as they are unique to testing.
"""

from tests.reference._case_factory import create_case

PENDLERS_CASE = create_case(
    case_name="Pendlers",
    expected_result={
        # Best compromise value
        "best_compromise_peak": 30.68181818,  # From screenshot (exact value)
        # Error metrics
        "max_error": 5.68181818,
        "num_experts": 22,
        # Median values - visible in the second screenshot
        "median_peak": 25.0,  # From "Median" value
        "median_lower": 25.0,  # Lower bound of median
        "median_upper": 25.0,  # Upper bound of median
        # Mean values
        "mean_peak": 36.36363636,  # From the phi value shown in Excel
    },
)
