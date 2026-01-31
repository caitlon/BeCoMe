"""Czech analysis utilities for BeCoMe examples."""


def calculate_agreement_level(
    max_error: float, thresholds: tuple[float, float] = (1.0, 3.0)
) -> str:
    """
    Determine expert agreement level based on maximum error (Czech labels).

    :param max_error: Maximum error value from BeCoMe calculation
    :param thresholds: Tuple of (good_threshold, moderate_threshold)
    :return: Agreement level string in Czech: "vysoká", "střední", or "nízká"
    """
    good_threshold, moderate_threshold = thresholds
    if max_error < good_threshold:
        return "vysoká"
    elif max_error < moderate_threshold:
        return "střední"
    else:
        return "nízká"
