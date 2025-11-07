"""
Utility functions for BeCoMe examples.

This package provides helper functions for loading data, formatting output,
displaying calculation steps, and analyzing results.
"""

# Re-export all public functions for backward compatibility
from .analysis import calculate_agreement_level
from .data_loading import load_data_from_txt
from .display import (
    display_median_calculation_details,
    display_step_1_arithmetic_mean,
    display_step_2_median,
    display_step_3_best_compromise,
    display_step_4_max_error,
)
from .formatting import display_case_header, display_centroid, print_header, print_section

__all__ = [
    # Data loading
    "load_data_from_txt",
    # Formatting
    "print_header",
    "print_section",
    "display_case_header",
    "display_centroid",
    # Display steps
    "display_step_1_arithmetic_mean",
    "display_step_2_median",
    "display_step_3_best_compromise",
    "display_step_4_max_error",
    "display_median_calculation_details",
    # Analysis
    "calculate_agreement_level",
]
