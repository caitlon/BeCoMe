"""
Pendlers (cross-border travel) case study from Excel reference implementation.

This case study contains data from the "CASE STUDY - PENDLERS" sheet
with 22 experts providing Likert scale ratings (0-25-50-75-100).

IMPORTANT: Expert opinions are loaded from examples/data/pendlers_case.txt
to avoid duplication. This file is the single source of truth for opinion data.
Only expected results are stored here as they are unique to testing.
"""

from pathlib import Path

from examples.utils import load_data_from_txt

# Load opinions from txt file (single source of truth)
_txt_file = Path(__file__).parent.parent.parent / "examples" / "data" / "pendlers_case.txt"
_opinions, _metadata = load_data_from_txt(str(_txt_file))

PENDLERS_CASE = {
    # Expert opinions data loaded from txt file
    "opinions": _opinions,
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
    # Description from txt file metadata
    "description": _metadata.get("description", "Pendlers case study"),
}
