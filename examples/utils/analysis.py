"""
Analysis utilities for BeCoMe examples.

This module provides functions for analyzing BeCoMe calculation results.
"""


def calculate_agreement_level(
    max_error: float, thresholds: tuple[float, float] = (1.0, 3.0)
) -> str:
    """
    Determine expert agreement level based on max error.

    Args:
        max_error: Maximum error value
        thresholds: Tuple of (good_threshold, moderate_threshold)

    Returns:
        Agreement level: "good", "moderate", or "low"
    """
    good_threshold, moderate_threshold = thresholds
    if max_error < good_threshold:
        return "good"
    elif max_error < moderate_threshold:
        return "moderate"
    else:
        return "low"
