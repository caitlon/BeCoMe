"""Analysis utilities for BeCoMe examples."""


def calculate_agreement_level(
    max_error: float, thresholds: tuple[float, float] = (1.0, 3.0)
) -> str:
    """
    Determine expert agreement level based on maximum error.

    :param max_error: Maximum error value from BeCoMe calculation
    :param thresholds: Tuple of (good_threshold, moderate_threshold)
    :return: Agreement level string: "good", "moderate", or "low"

    >>> calculate_agreement_level(0.5)
    'good'
    >>> calculate_agreement_level(2.0)
    'moderate'
    >>> calculate_agreement_level(5.0)
    'low'
    """
    good_threshold, moderate_threshold = thresholds
    if max_error < good_threshold:
        return "good"
    elif max_error < moderate_threshold:
        return "moderate"
    else:
        return "low"
